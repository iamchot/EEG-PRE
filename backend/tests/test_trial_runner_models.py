import importlib.util
from pathlib import Path

from app.models.dataset_collection import (
    BaselineKind,
    CollectionSession,
    CollectionTrial,
    TrialState,
)


def _load_trial_runner_migration():
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "20260719_02_trial_runner.py"
    )
    spec = importlib.util.spec_from_file_location("trial_runner_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RecordingOperations:
    def __init__(self):
        self.events = []

    def __getattr__(self, operation):
        def record(*args, **kwargs):
            self.events.append((operation, args, kwargs))

        return record


def test_trial_can_be_scheduled_without_rating_or_file():
    assert CollectionTrial.__table__.c.valence_rating.nullable is True
    assert CollectionTrial.__table__.c.arousal_rating.nullable is True
    assert CollectionTrial.__table__.c.confidence.nullable is True
    assert CollectionTrial.__table__.c.eeg_file_path.nullable is True
    assert CollectionTrial.__table__.c.eeg_checksum.nullable is True


def test_trial_lifecycle_columns_exist():
    columns = CollectionTrial.__table__.columns
    assert columns["state"].nullable is False
    assert {
        "rest_started_at",
        "stimulus_started_at",
        "rating_started_at",
        "failure_reason",
        "raw_size_bytes",
        "accepted_clean_seconds",
        "wall_clock_seconds",
    } <= set(columns.keys())


def test_runner_enums_have_exact_values():
    assert [kind.value for kind in BaselineKind] == ["eyes_open", "eyes_closed"]
    assert [state.value for state in TrialState] == [
        "scheduled",
        "rest",
        "stimulus",
        "rating",
        "completed",
        "interrupted",
        "failed",
    ]


def test_session_tracks_dual_baseline_progress_and_recovery():
    columns = CollectionSession.__table__.columns
    expected = {
        "eyes_open_accepted_clean_seconds",
        "eyes_open_wall_clock_seconds",
        "eyes_closed_accepted_clean_seconds",
        "eyes_closed_wall_clock_seconds",
        "active_baseline",
        "current_trial_id",
        "interruption_reason",
        "recovery_at",
    }
    assert expected <= set(columns.keys())
    assert columns["active_baseline"].nullable is True
    assert columns["current_trial_id"].nullable is True


def test_migration_backfills_legacy_trials_and_removes_temporary_defaults(monkeypatch):
    migration = _load_trial_runner_migration()
    operations = _RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    state_add_index = next(
        index
        for index, (operation, args, _) in enumerate(operations.events)
        if operation == "add_column" and args[1].name == "state"
    )
    state_add = operations.events[state_add_index][1][1]
    state_backfill_index = next(
        index
        for index, (operation, args, _) in enumerate(operations.events)
        if operation == "execute" and "SET state = 'completed'" in str(args[0])
    )
    state_alter_index = next(
        index
        for index, (operation, args, kwargs) in enumerate(operations.events)
        if operation == "alter_column"
        and args[:2] == ("collection_trials", "state")
        and kwargs.get("nullable") is False
    )
    assert state_add.nullable is True
    assert state_add_index < state_backfill_index < state_alter_index

    temporary_default_columns = {
        "eyes_open_accepted_clean_seconds",
        "eyes_open_wall_clock_seconds",
        "eyes_closed_accepted_clean_seconds",
        "eyes_closed_wall_clock_seconds",
        "accepted_clean_seconds",
        "wall_clock_seconds",
    }
    defaults_removed = {
        args[1]
        for operation, args, kwargs in operations.events
        if operation == "alter_column"
        and len(args) > 1
        and kwargs.get("server_default", "not-specified") is None
    }
    assert temporary_default_columns <= defaults_removed
