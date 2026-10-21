"""Six source tables. Cross-row accounting rules live in the services."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    text,
)

metadata = MetaData()
UTC_NOW = text("(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))")


def name_check():
    return CheckConstraint("length(name) BETWEEN 1 AND 100 AND name = trim(name)")


users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    name_check(),
)
groups = Table(
    "groups",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    name_check(),
)
group_members = Table(
    "group_members",
    metadata,
    Column("group_id", Integer, ForeignKey("groups.id"), primary_key=True, nullable=False),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True, nullable=False),
    Column("joined_at", Text, nullable=False, server_default=UTC_NOW),
)


def financial_columns():
    return [
        Column("id", Integer, primary_key=True),
        Column("group_id", Integer, ForeignKey("groups.id"), nullable=False),
        Column("recorded_by", Integer, nullable=False),
        Column("amount_paise", Integer, nullable=False),
        Column("created_at", Text, nullable=False, server_default=UTC_NOW),
        Column("request_id", Text, unique=True),
        Column("request_fingerprint", Text),
        CheckConstraint("typeof(amount_paise) = 'integer' AND amount_paise > 0"),
        CheckConstraint("(request_id IS NULL) = (request_fingerprint IS NULL)"),
        ForeignKeyConstraint(
            ["group_id", "recorded_by"], ["group_members.group_id", "group_members.user_id"]
        ),
    ]


expenses = Table(
    "expenses",
    metadata,
    *financial_columns(),
    Column("paid_by", Integer, nullable=False),
    Column("description", Text, nullable=False),
    CheckConstraint("length(description) BETWEEN 1 AND 500 AND description = trim(description)"),
    ForeignKeyConstraint(
        ["group_id", "paid_by"], ["group_members.group_id", "group_members.user_id"]
    ),
)
expense_shares = Table(
    "expense_shares",
    metadata,
    Column("expense_id", Integer, ForeignKey("expenses.id"), primary_key=True, nullable=False),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True, nullable=False),
    Column("share_paise", Integer, nullable=False),
    CheckConstraint("typeof(share_paise) = 'integer' AND share_paise >= 0"),
)
settlements = Table(
    "settlements",
    metadata,
    *financial_columns(),
    Column("from_user", Integer, nullable=False),
    Column("to_user", Integer, nullable=False),
    CheckConstraint("from_user <> to_user"),
    ForeignKeyConstraint(
        ["group_id", "from_user"], ["group_members.group_id", "group_members.user_id"]
    ),
    ForeignKeyConstraint(
        ["group_id", "to_user"], ["group_members.group_id", "group_members.user_id"]
    ),
)
Index("ix_expenses_history", expenses.c.group_id, expenses.c.created_at, expenses.c.id)
Index("ix_settlements_history", settlements.c.group_id, settlements.c.created_at, settlements.c.id)
Index("ix_shares_user", expense_shares.c.user_id)
