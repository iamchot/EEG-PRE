import pytest
from pydantic import ValidationError

from app.services.dataset_labels import DerivedLabels, derive_labels


@pytest.mark.parametrize(
    "score,label",
    [(1, "negative"), (4, "negative"), (6, "positive"), (9, "positive")],
)
def test_valence_boundaries(score, label):
    result = derive_labels(score, 6, 5)
    assert result.valence_label == label
    assert result.valid_valence_label is True


def test_score_five_invalidates_only_its_axis():
    result = derive_labels(5, 8, 5)
    assert result.valence_label is None
    assert result.valid_valence_label is False
    assert result.arousal_label == "high"
    assert result.valid_arousal_label is True


def test_low_confidence_invalidates_both_axes():
    result = derive_labels(8, 8, 2)
    assert result.valence_label == "positive"
    assert result.arousal_label == "high"
    assert result.valid_valence_label is False
    assert result.valid_arousal_label is False


def test_arousal_score_five_invalidates_only_arousal_axis():
    result = derive_labels(8, 5, 5)
    assert result.valence_label == "positive"
    assert result.valid_valence_label is True
    assert result.arousal_label is None
    assert result.valid_arousal_label is False


def test_both_score_fives_invalidate_both_axes():
    result = derive_labels(5, 5, 5)
    assert result.valence_label is None
    assert result.arousal_label is None
    assert result.valid_valence_label is False
    assert result.valid_arousal_label is False


def test_derived_labels_are_frozen():
    result = derive_labels(8, 8, 5)
    with pytest.raises(ValidationError):
        result.valence_label = "negative"


@pytest.mark.parametrize(
    "valence,arousal",
    [(0, 6), (10, 6), (6, 0), (6, 10)],
)
def test_rejects_scores_outside_one_through_nine(valence, arousal):
    with pytest.raises(ValidationError):
        derive_labels(valence, arousal, 5)


@pytest.mark.parametrize("confidence", [0, 6])
def test_rejects_confidence_outside_one_through_five(confidence):
    with pytest.raises(ValidationError):
        derive_labels(6, 6, confidence)


@pytest.mark.parametrize(
    "field,value",
    [
        ("valence", "6"),
        ("valence", 6.0),
        ("valence", True),
        ("arousal", "6"),
        ("arousal", 6.0),
        ("arousal", True),
        ("confidence", "5"),
        ("confidence", 5.0),
        ("confidence", True),
    ],
)
def test_rejects_non_strict_integer_ratings(field, value):
    ratings = {"valence": 6, "arousal": 6, "confidence": 5}
    ratings[field] = value
    with pytest.raises(ValidationError):
        derive_labels(**ratings)


@pytest.mark.parametrize(
    "labels",
    [
        {
            "valence_label": "low",
            "arousal_label": "high",
            "valid_valence_label": True,
            "valid_arousal_label": True,
        },
        {
            "valence_label": "positive",
            "arousal_label": "negative",
            "valid_valence_label": True,
            "valid_arousal_label": True,
        },
    ],
)
def test_rejects_axis_inappropriate_labels(labels):
    with pytest.raises(ValidationError):
        DerivedLabels(**labels)
