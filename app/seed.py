"""Explicit demo seed. Refuse a nonempty database instead of duplicating data."""
from sqlalchemy import select, func

from app import models as m
from app.accounting import split_equal
from app.database import make_engine, transaction


def seed(engine):
    with transaction(engine, write=True) as connection:
        if any(connection.execute(select(func.count()).select_from(table)).scalar_one()
               for table in (m.users, m.groups)):
            raise ValueError("Seed requires an empty database; existing records were left unchanged.")
        connection.execute(m.users.insert(), [dict(id=i, name=name) for i, name in
            [(1, "Mohit"), (2, "Rahul"), (3, "Ankit")]])
        connection.execute(m.groups.insert().values(id=1, name="Goa Trip"))
        connection.execute(m.group_members.insert(), [dict(group_id=1, user_id=i) for i in (1, 2, 3)])
        for record_id, (description, amount, payer, participants) in enumerate([
            ("Dinner", 120000, 1, [1, 2, 3]), ("Taxi", 60000, 2, [2, 3]),
            ("Snacks", 30000, 3, [1])], start=1):
            connection.execute(m.expenses.insert().values(id=record_id, group_id=1, paid_by=payer,
                recorded_by=payer, amount_paise=amount, description=description))
            connection.execute(m.expense_shares.insert(), [dict(share, expense_id=record_id)
                for share in split_equal(amount, participants)])


if __name__ == "__main__":
    engine = make_engine()
    try:
        seed(engine)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        engine.dispose()
    print("Pocket demo created: Goa Trip with Mohit, Rahul and Ankit.")
