from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset_collection import CollectionTrial, EmotionStimulus, TrialState
from app.schemas.dataset_collection import CollectionRunnerStateResponse


def collection_state_response(
    db: Session | None,
    state,
) -> CollectionRunnerStateResponse:
    """Build the one public runner-state DTO used by HTTP and WebSocket."""
    response = CollectionRunnerStateResponse.model_validate(state)
    if db is None:
        return response
    try:
        if response.current_trial_id is not None:
            row = db.execute(
                select(CollectionTrial.stimulus_id, EmotionStimulus.title)
                .join(EmotionStimulus, EmotionStimulus.id == CollectionTrial.stimulus_id)
                .where(CollectionTrial.id == response.current_trial_id)
            ).first()
            if row is None:
                return response
            return response.model_copy(
                update={
                    "current_stimulus_id": row.stimulus_id,
                    "current_stimulus_title": row.title,
                }
            )
        if response.next_trial_order is None:
            return response
        row = db.execute(
            select(CollectionTrial.id, CollectionTrial.stimulus_id, EmotionStimulus.title)
            .join(EmotionStimulus, EmotionStimulus.id == CollectionTrial.stimulus_id)
            .where(
                CollectionTrial.session_id == response.session_id,
                CollectionTrial.randomized_order == response.next_trial_order,
                CollectionTrial.state == TrialState.scheduled,
            )
        ).first()
        if row is None:
            return response
        return response.model_copy(
            update={
                "next_trial_id": row.id,
                "next_stimulus_id": row.stimulus_id,
                "next_stimulus_title": row.title,
            }
        )
    finally:
        try:
            db.rollback()
        except Exception:
            pass
