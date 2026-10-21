import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.database import transaction


def test_migration_and_foreign_keys(engine):
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version", "users", "groups", "group_members", "expenses", "expense_shares", "settlements"}
    for _ in range(3):
        with transaction(engine) as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    with pytest.raises(IntegrityError), transaction(engine, write=True) as connection:
        connection.exec_driver_sql("INSERT INTO group_members(group_id,user_id) VALUES (1,1)")


def test_migration_matches_models(engine):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.models import metadata
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), metadata) == []


def test_multi_query_read_keeps_one_snapshot(engine):
    # WAL lets a writer commit while this reader keeps its earlier snapshot.
    raw = engine.raw_connection()
    try:
        raw.cursor().execute("PRAGMA journal_mode=WAL")
    finally:
        raw.close()
    with transaction(engine) as reader:
        assert reader.exec_driver_sql("SELECT count(*) FROM users").scalar_one() == 0
        with transaction(engine, write=True) as writer:
            writer.exec_driver_sql("INSERT INTO users(name) VALUES ('New member')")
        assert reader.exec_driver_sql("SELECT count(*) FROM users").scalar_one() == 0
    with transaction(engine) as reader:
        assert reader.exec_driver_sql("SELECT count(*) FROM users").scalar_one() == 1


@pytest.mark.parametrize("sql", [
    "INSERT INTO users(name) VALUES (' ')",
    "INSERT INTO users(name) VALUES (NULL)",
    "INSERT INTO group_members(group_id,user_id) VALUES (1,1)",
    "INSERT INTO expenses(group_id,paid_by,recorded_by,amount_paise,description) VALUES (1,1,1,1.5,'x')",
    "INSERT INTO expenses(group_id,paid_by,recorded_by,amount_paise,description) VALUES (1,1,1,0,'x')",
    "INSERT INTO expenses(group_id,paid_by,recorded_by,amount_paise,description,request_id) VALUES (1,1,1,1,'x','id')",
    "INSERT INTO settlements(group_id,from_user,to_user,recorded_by,amount_paise) VALUES (1,1,1,1,1)",
    "INSERT INTO expense_shares(expense_id,user_id,share_paise) VALUES (999,1,1)",
])
def test_constraints(engine, sql):
    with transaction(engine, write=True) as connection:
        connection.exec_driver_sql("INSERT INTO users(id,name) VALUES (1,'One')")
        connection.exec_driver_sql("INSERT INTO groups(id,name) VALUES (1,'Trip')")
        connection.exec_driver_sql("INSERT INTO group_members(group_id,user_id) VALUES (1,1)")
    with pytest.raises(IntegrityError), transaction(engine, write=True) as connection:
        connection.exec_driver_sql(sql)
