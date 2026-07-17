import pytest
from pydantic import ValidationError

from app.services.dataset_labels import derive_labels


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
    assert result.valid_valence_label is False
    assert result.valid_arousal_label is False


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
