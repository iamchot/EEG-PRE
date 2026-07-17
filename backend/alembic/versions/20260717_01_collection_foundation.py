"""EEG collection foundation.

Revision ID: 20260717_01
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260717_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("dataset_participants",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("participant_code", sa.String(20), nullable=False, unique=True),
        sa.Column("consent_confirmed_at", sa.DateTime(), nullable=False), sa.Column("state", sa.Enum("active", "withdrawn", name="participantstate"), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_dataset_participants_participant_code", "dataset_participants", ["participant_code"])
    op.create_table("emotion_stimuli",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(150), nullable=False), sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False, unique=True), sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("target_quadrant", sa.Enum("positive_low", "positive_high", "negative_low", "negative_high", name="quadrant"), nullable=False),
        sa.Column("approval_state", sa.Enum("draft", "approved", "retired", name="stimulusapprovalstate"), nullable=False),
        sa.Column("stimulus_set_version", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_emotion_stimuli_target_quadrant", "emotion_stimuli", ["target_quadrant"])
    op.create_table("dataset_versions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("version", sa.String(30), unique=True, nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False), sa.Column("manifest_checksum", sa.String(64), unique=True, nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_table("model_versions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("version", sa.String(30), unique=True, nullable=False),
        sa.Column("dataset_version", sa.String(30), nullable=False), sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("artifact_checksum", sa.String(64), unique=True, nullable=False), sa.Column("metadata_json", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_table("collection_sessions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("participant_id", sa.Integer(), sa.ForeignKey("dataset_participants.id"), nullable=False),
        sa.Column("device_id", sa.String(100), nullable=False), sa.Column("device_name", sa.String(100)),
        sa.Column("eyes_open_baseline_path", sa.String(500)), sa.Column("eyes_open_baseline_checksum", sa.String(64)),
        sa.Column("eyes_closed_baseline_path", sa.String(500)), sa.Column("eyes_closed_baseline_checksum", sa.String(64)),
        sa.Column("completed_trials", sa.Integer(), nullable=False), sa.Column("total_trials", sa.Integer(), nullable=False),
        sa.Column("state", sa.Enum("preparation", "baseline", "ready", "in_progress", "completed", "interrupted", "withdrawn", "failed", name="collectionsessionstate"), nullable=False),
        sa.Column("started_at", sa.DateTime()), sa.Column("completed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_collection_sessions_participant_id", "collection_sessions", ["participant_id"])
    op.create_index("ix_collection_sessions_state", "collection_sessions", ["state"])
    op.create_table("collection_trials",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("collection_sessions.id"), nullable=False),
        sa.Column("stimulus_id", sa.Integer(), sa.ForeignKey("emotion_stimuli.id"), nullable=False), sa.Column("randomized_order", sa.Integer(), nullable=False),
        sa.Column("valence_rating", sa.Integer(), nullable=False), sa.Column("arousal_rating", sa.Integer(), nullable=False), sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("valence_label", sa.Boolean()), sa.Column("arousal_label", sa.Boolean()), sa.Column("valid_valence_label", sa.Boolean(), nullable=False), sa.Column("valid_arousal_label", sa.Boolean(), nullable=False),
        sa.Column("qc_summary_json", sa.Text()), sa.Column("eeg_file_path", sa.String(500), nullable=False), sa.Column("eeg_checksum", sa.String(64), nullable=False),
        sa.Column("review_state", sa.Enum("pending", "accepted", "rejected", name="reviewstate"), nullable=False), sa.Column("started_at", sa.DateTime()), sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("valence_rating BETWEEN 1 AND 9", name="ck_collection_trials_valence"), sa.CheckConstraint("arousal_rating BETWEEN 1 AND 9", name="ck_collection_trials_arousal"),
        sa.CheckConstraint("confidence BETWEEN 1 AND 5", name="ck_collection_trials_confidence"))
    op.create_index("ix_collection_trials_session_id", "collection_trials", ["session_id"])
    op.create_index("ix_collection_trials_stimulus_id", "collection_trials", ["stimulus_id"])
    op.create_index("ix_collection_trials_review_state", "collection_trials", ["review_state"])
    op.create_table("artifact_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("trial_id", sa.Integer(), sa.ForeignKey("collection_trials.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False), sa.Column("start_seconds", sa.Float(), nullable=False), sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("details_json", sa.Text()), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_artifact_events_trial_id", "artifact_events", ["trial_id"])


def downgrade() -> None:
    op.drop_table("artifact_events")
    op.drop_table("collection_trials")
    op.drop_table("collection_sessions")
    op.drop_table("model_versions")
    op.drop_table("dataset_versions")
    op.drop_table("emotion_stimuli")
    op.drop_table("dataset_participants")
