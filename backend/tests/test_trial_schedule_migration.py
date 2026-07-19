import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260719_03_trial_schedule_uniqueness.py"
    )
    spec = importlib.util.spec_from_file_location("trial_schedule_uniqueness_migration", migration_path)
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


def test_migration_adds_named_schedule_uniqueness_constraints(monkeypatch):
    migration = _load_migration()
    operations = _RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    assert migration.revision == "20260719_03"
    assert migration.down_revision == "20260719_02"
    assert operations.events == [
        (
            "create_unique_constraint",
            (
                "uq_collection_trials_session_randomized_order",
                "collection_trials",
                ["session_id", "randomized_order"],
            ),
            {},
        ),
    ]


def test_migration_downgrade_only_removes_schedule_constraints(monkeypatch):
    migration = _load_migration()
    operations = _RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    assert operations.events == [
        (
            "drop_constraint",
            ("uq_collection_trials_session_randomized_order", "collection_trials"),
            {"type_": "unique"},
        ),
    ]


def test_migration_emits_postgresql_unique_constraint_sql(monkeypatch):
    migration = _load_migration()
    output = StringIO()
    context = MigrationContext.configure(
        url="postgresql://",
        opts={"as_sql": True, "output_buffer": output},
    )
    monkeypatch.setattr(migration, "op", Operations(context))

    migration.upgrade()

    sql = output.getvalue()
    assert (
        "ALTER TABLE collection_trials ADD CONSTRAINT "
        "uq_collection_trials_session_randomized_order UNIQUE (session_id, randomized_order)"
    ) in sql
