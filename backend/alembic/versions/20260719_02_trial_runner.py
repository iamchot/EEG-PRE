"""Persist collection trial lifecycle.

Revision ID: 20260719_02
Revises: 20260717_01
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260719_02"
down_revision: Union[str, None] = "20260717_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


baseline_kind = sa.Enum("eyes_open", "eyes_closed", name="baselinekind")
trial_state = sa.Enum(
    "scheduled",
    "rest",
    "stimulus",
    "rating",
    "completed",
    "interrupted",
    "failed",
    name="trialstate",
)


def upgrade() -> None:
    op.add_column(
        "collection_sessions",
        sa.Column("eyes_open_accepted_clean_seconds", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collection_sessions",
        sa.Column("eyes_open_wall_clock_seconds", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collection_sessions",
        sa.Column("eyes_closed_accepted_clean_seconds", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collection_sessions",
        sa.Column("eyes_closed_wall_clock_seconds", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("collection_sessions", sa.Column("active_baseline", baseline_kind, nullable=True))
    op.add_column("collection_sessions", sa.Column("current_trial_id", sa.Integer(), nullable=True))
    op.add_column("collection_sessions", sa.Column("interruption_reason", sa.Text(), nullable=True))
    op.add_column("collection_sessions", sa.Column("recovery_at", sa.DateTime(), nullable=True))
    for column_name in (
        "eyes_open_accepted_clean_seconds",
        "eyes_open_wall_clock_seconds",
        "eyes_closed_accepted_clean_seconds",
        "eyes_closed_wall_clock_seconds",
    ):
        op.alter_column(
            "collection_sessions",
            column_name,
            existing_type=sa.Float(),
            server_default=None,
        )
    op.create_foreign_key(
        "fk_collection_sessions_current_trial_id",
        "collection_sessions",
        "collection_trials",
        ["current_trial_id"],
        ["id"],
    )
    op.create_index(
        "ix_collection_sessions_current_trial_id", "collection_sessions", ["current_trial_id"]
    )

    op.alter_column("collection_trials", "valence_rating", existing_type=sa.Integer(), nullable=True)
    op.alter_column("collection_trials", "arousal_rating", existing_type=sa.Integer(), nullable=True)
    op.alter_column("collection_trials", "confidence", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "collection_trials", "eeg_file_path", existing_type=sa.String(length=500), nullable=True
    )
    op.alter_column(
        "collection_trials", "eeg_checksum", existing_type=sa.String(length=64), nullable=True
    )
    op.add_column(
        "collection_trials",
        sa.Column("state", trial_state, nullable=True),
    )
    op.execute(sa.text("UPDATE collection_trials SET state = 'completed' WHERE state IS NULL"))
    op.alter_column(
        "collection_trials", "state", existing_type=trial_state, nullable=False, server_default=None
    )
    op.add_column("collection_trials", sa.Column("rest_started_at", sa.DateTime(), nullable=True))
    op.add_column("collection_trials", sa.Column("stimulus_started_at", sa.DateTime(), nullable=True))
    op.add_column("collection_trials", sa.Column("rating_started_at", sa.DateTime(), nullable=True))
    op.add_column("collection_trials", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column("collection_trials", sa.Column("raw_size_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "collection_trials",
        sa.Column("accepted_clean_seconds", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collection_trials",
        sa.Column("wall_clock_seconds", sa.Float(), nullable=False, server_default="0"),
    )
    for column_name in ("accepted_clean_seconds", "wall_clock_seconds"):
        op.alter_column(
            "collection_trials",
            column_name,
            existing_type=sa.Float(),
            server_default=None,
        )
    op.create_index("ix_collection_trials_state", "collection_trials", ["state"])


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Offline downgrade of 20260719_02 is unavailable because incomplete Trial rows "
            "must be checked against the live database first"
        )
    incomplete_count = op.get_bind().execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM collection_trials
            WHERE valence_rating IS NULL
               OR arousal_rating IS NULL
               OR confidence IS NULL
               OR eeg_file_path IS NULL
               OR eeg_checksum IS NULL
            """
        )
    ).scalar_one()
    if incomplete_count:
        raise RuntimeError(
            "Cannot downgrade 20260719_02: collection_trials contains incomplete rows "
            "with NULL ratings or EEG file metadata"
        )

    op.drop_index("ix_collection_trials_state", table_name="collection_trials")
    op.drop_column("collection_trials", "wall_clock_seconds")
    op.drop_column("collection_trials", "accepted_clean_seconds")
    op.drop_column("collection_trials", "raw_size_bytes")
    op.drop_column("collection_trials", "failure_reason")
    op.drop_column("collection_trials", "rating_started_at")
    op.drop_column("collection_trials", "stimulus_started_at")
    op.drop_column("collection_trials", "rest_started_at")
    op.drop_column("collection_trials", "state")
    op.alter_column(
        "collection_trials", "eeg_checksum", existing_type=sa.String(length=64), nullable=False
    )
    op.alter_column(
        "collection_trials", "eeg_file_path", existing_type=sa.String(length=500), nullable=False
    )
    op.alter_column("collection_trials", "confidence", existing_type=sa.Integer(), nullable=False)
    op.alter_column("collection_trials", "arousal_rating", existing_type=sa.Integer(), nullable=False)
    op.alter_column("collection_trials", "valence_rating", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_collection_sessions_current_trial_id", table_name="collection_sessions")
    op.drop_constraint(
        "fk_collection_sessions_current_trial_id", "collection_sessions", type_="foreignkey"
    )
    op.drop_column("collection_sessions", "recovery_at")
    op.drop_column("collection_sessions", "interruption_reason")
    op.drop_column("collection_sessions", "current_trial_id")
    op.drop_column("collection_sessions", "active_baseline")
    op.drop_column("collection_sessions", "eyes_closed_wall_clock_seconds")
    op.drop_column("collection_sessions", "eyes_closed_accepted_clean_seconds")
    op.drop_column("collection_sessions", "eyes_open_wall_clock_seconds")
    op.drop_column("collection_sessions", "eyes_open_accepted_clean_seconds")
