from app.models.dataset_collection import (
    ArtifactEvent,
    CollectionSession,
    CollectionTrial,
    DatasetParticipant,
    DatasetVersion,
    EmotionStimulus,
    ModelVersion,
)


COLLECTION_MODELS = (
    DatasetParticipant,
    EmotionStimulus,
    CollectionSession,
    CollectionTrial,
    ArtifactEvent,
    DatasetVersion,
    ModelVersion,
)


def test_collection_models_have_exact_table_names():
    assert [model.__tablename__ for model in COLLECTION_MODELS] == [
        "dataset_participants",
        "emotion_stimuli",
        "collection_sessions",
        "collection_trials",
        "artifact_events",
        "dataset_versions",
        "model_versions",
    ]


def test_collection_identity_is_pseudonymous():
    columns = set(DatasetParticipant.__table__.columns.keys())
    assert "participant_code" in columns
    assert {"name", "email", "phone", "password"}.isdisjoint(columns)
    assert DatasetParticipant.__table__.c.participant_code.unique is True


def test_stimulus_checksum_is_unique():
    assert EmotionStimulus.__table__.c.checksum.unique is True


def test_collection_tables_do_not_contain_direct_identity_columns():
    forbidden = {"name", "email", "phone", "password"}
    for model in COLLECTION_MODELS:
        assert forbidden.isdisjoint(model.__table__.columns.keys())
