from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.database import transaction
from app.main import create_app


def expense(client, group, ids, **changes):
    body = dict(paid_by=ids[0], recorded_by=ids[0], amount_paise=120000, description="Dinner")
    body.update(changes)
    return client.post(f"/groups/{group}/expenses", json=body)


def payment(client, group, ids, amount=40000, **changes):
    body = dict(from_user=ids[1], to_user=ids[0], recorded_by=ids[2], amount_paise=amount)
    body.update(changes)
    return client.post(f"/groups/{group}/settlements", json=body)


def test_pdf_dinner_and_settlement(client, trip):
    group, ids = trip
    response = expense(client, group, ids)
    assert response.status_code == 201
    assert response.json()["shares"] == [{"user_id": user, "share_paise": 40000} for user in ids]
    summary = client.get(f"/groups/{group}/balances").json()
    assert summary["suggested_payments"] == [
        {"from_user": user, "to_user": ids[0], "amount_paise": 40000} for user in ids[1:]]
    assert client.get(f"/groups/{group}/settlement-suggestions").json()["suggestions"] == summary["suggested_payments"]
    assert payment(client, group, ids).status_code == 201
    summary = client.get(f"/groups/{group}/balances").json()
    assert [member["net_balance_paise"] for member in summary["members"]] == [40000, 0, -40000]
    assert summary["total_expenses_paise"] == 120000


def test_recorder_participants_and_historical_shares(client, trip):
    group, ids = trip
    saved = expense(client, group, ids, recorded_by=ids[2], participant_ids=ids[1:], amount_paise=1).json()
    assert saved["shares"] == [{"user_id": ids[1], "share_paise": 1}, {"user_id": ids[2], "share_paise": 0}]
    new_user = client.post("/users", json={"name": "Mohit"}).json()["id"]
    client.post(f"/groups/{group}/members", json={"user_id": new_user})
    assert client.get(f"/groups/{group}/expenses").json()["items"][0] == saved
    summary = client.get(f"/groups/{group}/balances").json()
    assert summary["members"][-1]["net_balance_paise"] == 0
    assert len(summary["members"]) == 4


@pytest.mark.parametrize("amount", [0, -1, 1.5, "100", True, 2**63])
def test_strict_money(client, trip, amount):
    group, ids = trip
    assert expense(client, group, ids, amount_paise=amount).status_code == 422
    assert payment(client, group, ids, amount=amount).status_code == 422


@pytest.mark.parametrize("participants", [[], None, [1, 1]])
def test_invalid_participants(client, trip, participants):
    group, ids = trip
    assert expense(client, group, ids, participant_ids=participants).status_code == 422


def test_validation_order_and_names(client, trip):
    group, ids = trip
    outsider = client.post("/users", json={"name": "Mohit"}).json()["id"]
    assert expense(client, group, ids, paid_by=outsider).status_code == 422
    assert expense(client, group, ids, paid_by=9999).status_code == 404
    assert expense(client, 9999, ids).status_code == 404
    assert client.post(f"/groups/{group}/members", json={"user_id": ids[0]}).status_code == 409
    for path in ("/users", "/groups"):
        for name in (" ", "x" * 101):
            response = client.post(path, json={"name": name})
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "validation_error"
        assert client.post(path, json={"name": "  Duplicate  "}).json()["name"] == "Duplicate"
        assert client.post(path, json={"name": "Duplicate"}).status_code == 201


def test_repayments_and_new_obligations(client, trip):
    group, ids = trip
    expense(client, group, ids)
    assert payment(client, group, ids, from_user=ids[0], to_user=ids[0]).status_code == 422
    assert payment(client, group, ids, amount=40001).status_code == 409
    assert payment(client, group, ids, amount=15000).status_code == 201
    assert payment(client, group, ids, amount=25000).status_code == 201
    assert payment(client, group, ids).status_code == 409
    assert payment(client, group, ids, from_user=ids[2]).status_code == 201
    assert client.get(f"/groups/{group}/balances").json()["total_outstanding_paise"] == 0
    expense(client, group, ids, amount_paise=300)
    assert client.get(f"/groups/{group}/balances").json()["total_outstanding_paise"] == 200


def test_replay_and_conflict(client, trip):
    group, ids = trip
    request_id = str(uuid4())
    first = expense(client, group, ids, request_id=request_id)
    replay = expense(client, group, ids, request_id=request_id)
    assert first.status_code == 201 and replay.status_code == 200
    assert first.json() == replay.json()
    new_user = client.post("/users", json={"name": "Later"}).json()["id"]
    client.post(f"/groups/{group}/members", json={"user_id": new_user})
    assert expense(client, group, ids, request_id=request_id).json() == first.json()
    for changes in (dict(amount_paise=1), dict(description="Other"), dict(paid_by=ids[1]),
                    dict(recorded_by=ids[1]), dict(participant_ids=ids)):
        assert expense(client, group, ids, request_id=request_id, **changes).status_code == 409
    key = str(uuid4())
    assert expense(client, group, ids, request_id=key, participant_ids=list(reversed(ids))).status_code == 201
    assert expense(client, group, ids, request_id=key, participant_ids=ids).status_code == 200
    key = str(uuid4())
    first = payment(client, group, ids, amount=80000, request_id=key)
    assert first.status_code == 201
    assert payment(client, group, ids, amount=80000, request_id=key).status_code == 200
    assert payment(client, group, ids, amount=1, request_id=key).status_code == 409
    assert "fingerprint" not in first.text
    assert "fingerprint" not in client.get("/openapi.json").text


def test_unkeyed_history_and_group_isolation(client, trip):
    group, ids = trip
    for _ in range(3):
        assert expense(client, group, ids).status_code == 201
    page = client.get(f"/groups/{group}/expenses?limit=1&offset=1").json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert page["items"][0]["id"] == 2
    assert page["items"][0]["recorded_by"] == ids[0]
    assert client.get(f"/groups/{group}/expenses?limit=101").status_code == 422
    assert client.get(f"/groups/{group}/settlements?offset=-1").status_code == 422
    empty = client.post("/groups", json={"name": "Empty"}).json()["id"]
    assert client.get(f"/groups/{empty}/balances").json()["members"] == []
    client.post(f"/groups/{empty}/members", json={"user_id": ids[0]})
    expense(client, empty, ids, amount_paise=5)
    assert client.get(f"/groups/{empty}/balances").json()["total_outstanding_paise"] == 0


def test_share_failure_rolls_back(client, trip, engine):
    group, ids = trip

    def fail(connection, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO expense_shares"):
            raise RuntimeError("forced share insertion failure")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            expense(client, group, ids)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert client.get(f"/groups/{group}/expenses").json()["total"] == 0


def test_separate_connection_concurrent_payments(client, trip, engine):
    group, ids = trip
    expense(client, group, ids)

    def send(key):
        with TestClient(create_app(engine)) as other:
            return payment(other, group, ids, amount=30000, request_id=key).status_code

    with ThreadPoolExecutor(2) as pool:
        statuses = list(pool.map(send, [str(uuid4()), str(uuid4())]))
    assert sorted(statuses) == [201, 409]


def test_concurrent_identical_requests(client, trip, engine):
    group, ids = trip
    key = str(uuid4())

    def send(_):
        with TestClient(create_app(engine)) as other:
            return expense(other, group, ids, request_id=key).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(send, range(2))) == [200, 201]
    assert client.get(f"/groups/{group}/expenses").json()["total"] == 1


def test_held_lock_returns_retryable_error(client, trip, engine):
    group, ids = trip
    with transaction(engine, write=True):
        response = expense(client, group, ids, request_id=str(uuid4()))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_busy"
    assert client.get(f"/groups/{group}/expenses").json()["total"] == 0


def test_raw_share_integrity(engine, trip):
    with pytest.raises(IntegrityError), transaction(engine, write=True) as connection:
        connection.exec_driver_sql("INSERT INTO expense_shares(expense_id,user_id,share_paise) VALUES (NULL,1,-1)")
