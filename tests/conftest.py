import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.database import make_engine


@pytest.fixture
def engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    engine = make_engine(url, busy_ms=100)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    from app.main import create_app
    with TestClient(create_app(engine)) as client:
        yield client


@pytest.fixture
def trip(client):
    ids = [client.post("/users", json={"name": name}).json()["id"]
           for name in ("Mohit", "Rahul", "Ankit")]
    group = client.post("/groups", json={"name": "Goa Trip"}).json()["id"]
    for user in ids:
        assert client.post(f"/groups/{group}/members", json={"user_id": user}).status_code == 201
    return group, ids
