"""question sets generated from conversations

Revision ID: 003
Revises: 002
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "question_sets" in inspector.get_table_names():
        return
    op.create_table(
        "question_sets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(length=36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("used_documents", sa.Boolean(), nullable=False),
        sa.Column("has_relevant_match", sa.Boolean(), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False),
        sa.Column("questions_json", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_question_sets_conversation_id", "question_sets", ["conversation_id"])
    op.create_index("ix_question_sets_user_id", "question_sets", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "question_sets" not in inspector.get_table_names():
        return
    op.drop_index("ix_question_sets_conversation_id", table_name="question_sets")
    op.drop_index("ix_question_sets_user_id", table_name="question_sets")
    op.drop_table("question_sets")
