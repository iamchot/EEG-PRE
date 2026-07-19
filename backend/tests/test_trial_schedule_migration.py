import importlib.util
import os
import re
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.environment import EnvironmentContext
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import get_settings


_MYSQL_TEST_DATABASE_PATTERN = re.compile(r"eegpre_migration_test_[0-9a-f]{32}")


def _guard_mysql_test_database_name(database_name):
    assert _MYSQL_TEST_DATABASE_PATTERN.fullmatch(database_name)
    assert database_name != make_url(get_settings().database_url).database


@pytest.fixture
def mysql_migration_database_url():
    configured_url = make_url(
        os.getenv("EEGPRE_MYSQL_TEST_ADMIN_URL", get_settings().database_url)
    )
    if configured_url.get_backend_name() != "mysql":
        pytest.skip("MySQL migration integration requires a configured MySQL DATABASE_URL")

    database_name = f"eegpre_migration_test_{uuid4().hex}"
    _guard_mysql_test_database_name(database_name)
    server_engine = create_engine(configured_url.set(database=None), isolation_level="AUTOCOMMIT")
    try:
        with server_engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4")
    except SQLAlchemyError as exc:
        server_engine.dispose()
        pytest.skip(f"MySQL migration integration unavailable: {type(exc).__name__}")

    try:
        yield configured_url.set(database=database_name)
    finally:
        _guard_mysql_test_database_name(database_name)
        with server_engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE `{database_name}`")
        server_engine.dispose()


def _upgrade_on_bound_connection(connection, destination_revision):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    script = ScriptDirectory.from_config(config)

    def upgrade_revisions(current_revision, context):
        return script._upgrade_revs(destination_revision, current_revision)

    with EnvironmentContext(
        config,
        script,
        fn=upgrade_revisions,
        destination_rev=destination_revision,
    ) as environment:
        environment.configure(connection=connection)
        with environment.begin_transaction():
            environment.run_migrations()


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


def test_migration_emits_mysql_upgrade_and_downgrade_sql(monkeypatch):
    migration = _load_migration()
    upgrade_output = StringIO()
    upgrade_context = MigrationContext.configure(
        url="mysql+pymysql://",
        opts={"as_sql": True, "output_buffer": upgrade_output},
    )
    monkeypatch.setattr(migration, "op", Operations(upgrade_context))

    migration.upgrade()

    assert (
        "ALTER TABLE collection_trials ADD CONSTRAINT "
        "uq_collection_trials_session_randomized_order UNIQUE (session_id, randomized_order)"
    ) in upgrade_output.getvalue()

    downgrade_output = StringIO()
    downgrade_context = MigrationContext.configure(
        url="mysql+pymysql://",
        opts={"as_sql": True, "output_buffer": downgrade_output},
    )
    monkeypatch.setattr(migration, "op", Operations(downgrade_context))

    migration.downgrade()

    assert (
        "ALTER TABLE collection_trials DROP INDEX "
        "uq_collection_trials_session_randomized_order"
    ) in downgrade_output.getvalue()


def test_mysql_upgrade_rejects_duplicate_orders_without_partial_ddl(
    mysql_migration_database_url,
):
    engine = create_engine(mysql_migration_database_url)
    try:
        with engine.connect() as connection:
            _upgrade_on_bound_connection(connection, "20260719_02")

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO dataset_participants
                        (participant_code, consent_confirmed_at, state)
                    VALUES ('MIGRATION-P001', '2026-01-01 00:00:00', 'active')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO emotion_stimuli
                        (title, file_path, checksum, duration_seconds, target_quadrant,
                         approval_state, stimulus_set_version)
                    VALUES
                        ('one', 'one.mp4', :checksum_one, 45, 'positive_low', 'approved', 'v1'),
                        ('two', 'two.mp4', :checksum_two, 45, 'positive_low', 'approved', 'v1')
                    """
                ),
                {"checksum_one": "1" * 64, "checksum_two": "2" * 64},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO collection_sessions
                        (participant_id, completed_trials, total_trials, state,
                         eyes_open_accepted_clean_seconds, eyes_open_wall_clock_seconds,
                         eyes_closed_accepted_clean_seconds, eyes_closed_wall_clock_seconds)
                    VALUES (1, 0, 2, 'preparation', 0, 0, 0, 0)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO collection_trials
                        (session_id, stimulus_id, randomized_order,
                         valid_valence_label, valid_arousal_label, review_state, state,
                         accepted_clean_seconds, wall_clock_seconds)
                    VALUES
                        (1, 1, 1, 0, 0, 'pending', 'scheduled', 0, 0),
                        (1, 2, 1, 0, 0, 'pending', 'scheduled', 0, 0)
                    """
                )
            )

        with engine.connect() as connection:
            with pytest.raises(IntegrityError):
                _upgrade_on_bound_connection(connection, "20260719_03")
            connection.rollback()

        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260719_02"
            unique_names = {
                constraint["name"]
                for constraint in inspect(connection).get_unique_constraints("collection_trials")
            }
            assert "uq_collection_trials_session_randomized_order" not in unique_names
            assert connection.scalar(text("SELECT COUNT(*) FROM collection_trials")) == 2
    finally:
        engine.dispose()
