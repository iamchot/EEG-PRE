"""Enforce one complete trial schedule identity per collection session.

Revision ID: 20260719_03
Revises: 20260719_02
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260719_03"
down_revision: Union[str, None] = "20260719_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_collection_trials_session_randomized_order",
        "collection_trials",
        ["session_id", "randomized_order"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_collection_trials_session_randomized_order",
        "collection_trials",
        type_="unique",
    )
