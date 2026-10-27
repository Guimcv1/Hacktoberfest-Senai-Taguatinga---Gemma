"""optional documents on conversations

Revision ID: 002
Revises: 001
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "fk_conversations_document_id_documents"


def _document_fk_names(connection) -> list[str]:
    inspector = sa.inspect(connection)
    names: list[str] = []
    for foreign_key in inspector.get_foreign_keys("conversations"):
        if foreign_key.get("referred_table") == "documents" and list(
            foreign_key.get("constrained_columns") or []
        ) == ["document_id"]:
            if foreign_key.get("name"):
                names.append(foreign_key["name"])
    return names


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "conversation_documents" not in inspector.get_table_names():
        op.create_table(
            "conversation_documents",
            sa.Column(
                "conversation_id",
                sa.String(length=36),
                sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "document_id",
                sa.String(length=36),
                sa.ForeignKey("documents.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
        )
        op.create_index(
            "ix_conversation_documents_document_id",
            "conversation_documents",
            ["document_id"],
        )
        bind.execute(
            sa.text(
                "INSERT INTO conversation_documents (conversation_id, document_id) "
                "SELECT id, document_id FROM conversations WHERE document_id IS NOT NULL"
            )
        )

    existing = _document_fk_names(bind)
    with op.batch_alter_table("conversations") as batch:
        for name in existing:
            batch.drop_constraint(name, type_="foreignkey")
        batch.alter_column("document_id", existing_type=sa.String(length=36), nullable=True)
        batch.create_foreign_key(
            _FK_NAME,
            "documents",
            ["document_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM conversations WHERE document_id IS NULL "
            "AND id NOT IN (SELECT conversation_id FROM conversation_documents)"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE conversations SET document_id = ("
            "SELECT document_id FROM conversation_documents "
            "WHERE conversation_documents.conversation_id = conversations.id "
            "LIMIT 1"
            ") WHERE document_id IS NULL"
        )
    )
    bind.execute(sa.text("DELETE FROM conversations WHERE document_id IS NULL"))

    existing = _document_fk_names(bind)
    with op.batch_alter_table("conversations") as batch:
        for name in existing:
            batch.drop_constraint(name, type_="foreignkey")
        batch.alter_column("document_id", existing_type=sa.String(length=36), nullable=False)
        batch.create_foreign_key(
            _FK_NAME,
            "documents",
            ["document_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.drop_index("ix_conversation_documents_document_id", table_name="conversation_documents")
    op.drop_table("conversation_documents")
