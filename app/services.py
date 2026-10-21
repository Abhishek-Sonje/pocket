"""Small synchronous services own complete transactions."""

import hashlib
import json

from sqlalchemy import func, select

from app import models as m
from app.accounting import split_equal, summarize
from app.database import transaction
from app.errors import AppError


def require(connection, table, record_id):
    row = connection.execute(select(table).where(table.c.id == record_id)).mappings().first()
    if row is None:
        raise AppError(
            404, "not_found", f"{table.name.rstrip('s').capitalize()} #{record_id} does not exist."
        )
    return dict(row)


def create_named(engine, table, name):
    with transaction(engine, write=True) as connection:
        record_id = connection.execute(table.insert().values(name=name)).inserted_primary_key[0]
        return require(connection, table, record_id)


def list_named(engine, table):
    with transaction(engine) as connection:
        return [
            dict(row) for row in connection.execute(select(table).order_by(table.c.id)).mappings()
        ]


def members_in(connection, group_id):
    return [
        dict(row)
        for row in connection.execute(
            select(m.group_members, m.users.c.name)
            .join(m.users)
            .where(m.group_members.c.group_id == group_id)
            .order_by(m.users.c.id)
        ).mappings()
    ]


def list_members(engine, group_id):
    with transaction(engine) as connection:
        require(connection, m.groups, group_id)
        return members_in(connection, group_id)


def add_member(engine, group_id, user_id):
    with transaction(engine, write=True) as connection:
        require(connection, m.groups, group_id)
        require(connection, m.users, user_id)
        if user_id in {member["user_id"] for member in members_in(connection, group_id)}:
            raise AppError(409, "already_member", "This user already belongs to the group.")
        connection.execute(m.group_members.insert().values(group_id=group_id, user_id=user_id))
        return dict(
            connection.execute(
                select(m.group_members).where(
                    m.group_members.c.group_id == group_id, m.group_members.c.user_id == user_id
                )
            )
            .mappings()
            .one()
        )


def validate_parties(connection, group_id, user_ids):
    require(connection, m.groups, group_id)
    for user_id in sorted(set(user_ids)):
        require(connection, m.users, user_id)
    members = members_in(connection, group_id)
    if not set(user_ids).issubset({member["user_id"] for member in members}):
        raise AppError(
            422,
            "not_member",
            "Every payer, recorder, participant and repayment party must belong to this group.",
        )
    return members


def balances_in(connection, group_id):
    require(connection, m.groups, group_id)
    expenses = (
        connection.execute(select(m.expenses).where(m.expenses.c.group_id == group_id))
        .mappings()
        .all()
    )
    shares = (
        connection.execute(
            select(m.expense_shares).join(m.expenses).where(m.expenses.c.group_id == group_id)
        )
        .mappings()
        .all()
    )
    settlements = (
        connection.execute(select(m.settlements).where(m.settlements.c.group_id == group_id))
        .mappings()
        .all()
    )
    return summarize(group_id, members_in(connection, group_id), expenses, shares, settlements)


def balances(engine, group_id):
    with transaction(engine) as connection:
        return balances_in(connection, group_id)


def fingerprint(group_id, body):
    data = body.model_dump(mode="json", exclude={"request_id"})
    if data.get("participant_ids") is not None:
        data["participant_ids"] = sorted(data["participant_ids"])
    data["group_id"] = group_id
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def financial_result(connection, table, row):
    result = {
        key: value
        for key, value in dict(row).items()
        if key not in ("request_id", "request_fingerprint")
    }
    if table is m.expenses:
        result["shares"] = [
            dict(share)
            for share in connection.execute(
                select(m.expense_shares.c.user_id, m.expense_shares.c.share_paise)
                .where(m.expense_shares.c.expense_id == row["id"])
                .order_by(m.expense_shares.c.user_id)
            ).mappings()
        ]
    return result


def create_financial(engine, group_id, body, *, expense):
    table = m.expenses if expense else m.settlements
    request_id = str(body.request_id) if body.request_id else None
    digest = fingerprint(group_id, body) if request_id else None
    with transaction(engine, write=True) as connection:
        if request_id:
            saved = (
                connection.execute(select(table).where(table.c.request_id == request_id))
                .mappings()
                .first()
            )
            if saved:
                if saved["request_fingerprint"] != digest:
                    raise AppError(
                        409,
                        "request_id_conflict",
                        "This request ID was already used with different input.",
                    )
                return financial_result(connection, table, saved), True

        parties = [body.recorded_by]
        if expense:
            parties += [body.paid_by] + (body.participant_ids or [])
        else:
            parties += [body.from_user, body.to_user]
        members = validate_parties(connection, group_id, parties)
        shares = []
        if expense:
            participants = (
                body.participant_ids
                if body.participant_ids is not None
                else [member["user_id"] for member in members]
            )
            if not participants:
                raise AppError(
                    422, "no_participants", "Add group members before recording an expense."
                )
            shares = split_equal(body.amount_paise, participants)
            if sum(share["share_paise"] for share in shares) != body.amount_paise:
                raise RuntimeError("Expense shares do not match the amount.")
        else:
            summary = balances_in(connection, group_id)
            nets = {member["user_id"]: member["net_balance_paise"] for member in summary["members"]}
            debt, credit = -nets[body.from_user], nets[body.to_user]
            if debt <= 0 or credit <= 0:
                raise AppError(
                    409,
                    "incompatible_balances",
                    "The sender must owe money and the recipient must be owed money.",
                )
            if body.amount_paise > min(debt, credit):
                raise AppError(
                    409,
                    "repayment_exceeds_balance",
                    "This repayment exceeds the remaining debt or credit.",
                )

        values = body.model_dump(exclude={"participant_ids", "request_id"})
        values.update(group_id=group_id, request_id=request_id, request_fingerprint=digest)
        record_id = connection.execute(table.insert().values(**values)).inserted_primary_key[0]
        if expense:
            connection.execute(
                m.expense_shares.insert(), [dict(share, expense_id=record_id) for share in shares]
            )
        return financial_result(connection, table, require(connection, table, record_id)), False


def history(engine, group_id, table, limit, offset):
    with transaction(engine) as connection:
        require(connection, m.groups, group_id)
        condition = table.c.group_id == group_id
        total = connection.execute(
            select(func.count()).select_from(table).where(condition)
        ).scalar_one()
        rows = (
            connection.execute(
                select(table)
                .where(condition)
                .order_by(table.c.created_at.desc(), table.c.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        return {
            "items": [financial_result(connection, table, row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
