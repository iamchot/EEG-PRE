# Task Brief

## Global Constraints

- This system is for entertainment and prototype research, not medical diagnosis or treatment.
- Supported participant identifiers are pseudonymous codes such as `P001`; do not store names, email addresses, or phone numbers in collection tables.
- Supported quadrants are exactly `positive_low`, `positive_high`, `negative_low`, and `negative_high`.
- Valence/Arousal scores are integers from 1 through 9; Confidence is an integer from 1 through 5.
- Score 5 is ambiguous for its axis. Confidence below 3 invalidates both training labels.
- Collection, review, export, and stimulus administration remain Admin-only.
- Do not modify ordinary User EEG/comic endpoints or the EEG WebSocket contract.
- Raw EEG and stimulus media are file references with checksums; never store binary data in MySQL.
- All new Angular component CSS must be in `.css` files, not inline `styles` metadata.
- Preserve unrelated working-tree changes and stage only the files named by each task.


### Task 2: Label Derivation and Foundation Validation

**Files:**

- Create: `backend/app/services/dataset_labels.py`
- Create: `backend/tests/test_dataset_labels.py`

**Interfaces:**

- Produces `AxisLabel = Literal["negative", "positive", "low", "high"]`.
- Produces immutable `DerivedLabels` with `valence_label`, `arousal_label`, `valid_valence_label`, `valid_arousal_label`.
- Produces `derive_labels(valence: int, arousal: int, confidence: int) -> DerivedLabels`.

- [ ] **Step 1: Write the label boundary tests**

```python
import pytest
from pydantic import ValidationError

from app.services.dataset_labels import derive_labels


@pytest.mark.parametrize("score,label", [(1, "negative"), (4, "negative"), (6, "positive"), (9, "positive")])
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
```

Add parameterized rejection tests for scores outside 1–9 and Confidence outside 1–5.

- [ ] **Step 2: Run tests and verify RED**

Expected: import failure for `dataset_labels`.

- [ ] **Step 3: Implement the pure label service**

Use a frozen Pydantic model so invalid ranges fail consistently:

```python
class RatingInput(BaseModel):
    valence: int = Field(ge=1, le=9)
    arousal: int = Field(ge=1, le=9)
    confidence: int = Field(ge=1, le=5)


def derive_labels(valence: int, arousal: int, confidence: int) -> DerivedLabels:
    rating = RatingInput(valence=valence, arousal=arousal, confidence=confidence)
    confident = rating.confidence >= 3
    return DerivedLabels(
        valence_label=None if rating.valence == 5 else ("negative" if rating.valence <= 4 else "positive"),
        arousal_label=None if rating.arousal == 5 else ("low" if rating.arousal <= 4 else "high"),
        valid_valence_label=confident and rating.valence != 5,
        valid_arousal_label=confident and rating.arousal != 5,
    )
```

- [ ] **Step 4: Run focused tests and commit**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_dataset_labels.py -q
git add -- backend/app/services/dataset_labels.py backend/tests/test_dataset_labels.py
git commit -m "feat: define EEG dataset label rules"
```

## Report Contract
Write .superpowers/sdd/eeg-foundation-task-2-report.md with files changed, RED/GREEN evidence, commit hash, self-review, and concerns. Return only status, commit hash, one-line test summary, and concerns.

