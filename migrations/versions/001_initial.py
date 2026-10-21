"""Pocket's initial source-record schema. Keep this migration independent of app models."""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for name in ("users", "groups"):
        op.create_table(
            name,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.Text, nullable=False),
            sa.CheckConstraint("length(name) BETWEEN 1 AND 100 AND name = trim(name)"),
        )
    now = sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))")
    op.create_table(
        "group_members",
        sa.Column(
            "group_id", sa.Integer, sa.ForeignKey("groups.id"), primary_key=True, nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True, nullable=False
        ),
        sa.Column("joined_at", sa.Text, nullable=False, server_default=now),
    )
    for name, parties in (("expenses", ("paid_by",)), ("settlements", ("from_user", "to_user"))):
        columns = [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id"), nullable=False),
            sa.Column("recorded_by", sa.Integer, nullable=False),
            sa.Column("amount_paise", sa.Integer, nullable=False),
            sa.Column("created_at", sa.Text, nullable=False, server_default=now),
            sa.Column("request_id", sa.Text, unique=True),
            sa.Column("request_fingerprint", sa.Text),
            sa.CheckConstraint("typeof(amount_paise) = 'integer' AND amount_paise > 0"),
            sa.CheckConstraint("(request_id IS NULL) = (request_fingerprint IS NULL)"),
        ]
        for party in parties:
            columns.append(sa.Column(party, sa.Integer, nullable=False))
        for party in (*parties, "recorded_by"):
            columns.append(
                sa.ForeignKeyConstraint(
                    ["group_id", party], ["group_members.group_id", "group_members.user_id"]
                )
            )
        if name == "expenses":
            columns.extend(
                [
                    sa.Column("description", sa.Text, nullable=False),
                    sa.CheckConstraint(
                        "length(description) BETWEEN 1 AND 500 AND description = trim(description)"
                    ),
                ]
            )
        else:
            columns.append(sa.CheckConstraint("from_user <> to_user"))
        op.create_table(name, *columns)
        op.create_index(f"ix_{name}_history", name, ["group_id", "created_at", "id"])
    op.create_table(
        "expense_shares",
        sa.Column(
            "expense_id", sa.Integer, sa.ForeignKey("expenses.id"), primary_key=True, nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True, nullable=False
        ),
        sa.Column("share_paise", sa.Integer, nullable=False),
        sa.CheckConstraint("typeof(share_paise) = 'integer' AND share_paise >= 0"),
    )
    op.create_index("ix_shares_user", "expense_shares", ["user_id"])


def downgrade():
    for name in ("expense_shares", "settlements", "expenses", "group_members", "groups", "users"):
        op.drop_table(name)
