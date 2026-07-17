from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.middleware.auth_middleware import StandardUser
from app.models.comic import Comic, Rating
from app.models.eeg import EEGSession, EmotionResult
from app.models.persona import Persona
from app.schemas.comic import ComicGenerateRequest, ComicOut, RatingCreate, RatingOut
from app.services.gemini_service import generate_comic_story
from app.services.diffusion_service import generate_all_panels

router = APIRouter(prefix="/comics", tags=["comics"])


@router.post("/generate", response_model=ComicOut, status_code=status.HTTP_201_CREATED)
async def generate_comic(
    body: ComicGenerateRequest,
    current_user: StandardUser,
    db: Session = Depends(get_db),
):
    """
    Generate a 4-panel comic from EEG emotion + story input.
    Requires a completed EEG session with EmotionResult.
    """
    # Fetch emotion result from session
    eeg_session = db.query(EEGSession).filter(
        EEGSession.id == body.session_id,
        EEGSession.user_id == current_user.id,
    ).first()
    if not eeg_session:
        raise HTTPException(status_code=404, detail="EEG session not found")

    emotion_result = db.query(EmotionResult).filter(
        EmotionResult.session_id == body.session_id
    ).first()
    if not emotion_result:
        raise HTTPException(status_code=400, detail="Emotion result not available for this session")

    persona = None
    if body.persona_id:
        persona = db.query(Persona).filter(
            Persona.id == body.persona_id,
            Persona.user_id == current_user.id,
        ).first()

    # Generate story with Gemini
    story = await generate_comic_story(
        input_story=body.input_story,
        emotion=emotion_result.final_emotion.value,
        art_style=body.art_style,
        persona_name=persona.persona_name if persona else None,
        persona_appearance=persona.appearance if persona else None,
    )

    # Generate images with ComfyUI
    descriptions = [p.scene_description for p in story.panels]
    panel_urls = await generate_all_panels(descriptions, body.art_style)

    # Persist comic
    comic = Comic(
        user_id=current_user.id,
        session_id=body.session_id,
        persona_id=body.persona_id,
        input_story=body.input_story,
        generated_prompt=story.full_prompt,
        panel_1_url=panel_urls[0] if len(panel_urls) > 0 else None,
        panel_2_url=panel_urls[1] if len(panel_urls) > 1 else None,
        panel_3_url=panel_urls[2] if len(panel_urls) > 2 else None,
        panel_4_url=panel_urls[3] if len(panel_urls) > 3 else None,
        panel_1_dialogue=story.panels[0].dialogue if len(story.panels) > 0 else None,
        panel_2_dialogue=story.panels[1].dialogue if len(story.panels) > 1 else None,
        panel_3_dialogue=story.panels[2].dialogue if len(story.panels) > 2 else None,
        panel_4_dialogue=story.panels[3].dialogue if len(story.panels) > 3 else None,
    )
    db.add(comic)
    db.commit()
    db.refresh(comic)

    out = ComicOut.model_validate(comic)
    out.emotion = emotion_result.final_emotion.value
    out.persona_name = persona.persona_name if persona else None
    return out


@router.get("/", response_model=list[ComicOut])
def list_comics(
    current_user: StandardUser,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    comics = (
        db.query(Comic)
        .filter(Comic.user_id == current_user.id)
        .order_by(Comic.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    results = []
    for c in comics:
        out = ComicOut.model_validate(c)
        # JOIN emotion
        if c.session_id:
            er = db.query(EmotionResult).filter(EmotionResult.session_id == c.session_id).first()
            if er:
                out.emotion = er.final_emotion.value
        # JOIN persona
        if c.persona:
            out.persona_name = c.persona.persona_name
        results.append(out)
    return results


@router.get("/{comic_id}", response_model=ComicOut)
def get_comic(comic_id: int, current_user: StandardUser, db: Session = Depends(get_db)):
    comic = db.query(Comic).filter(
        Comic.id == comic_id, Comic.user_id == current_user.id
    ).first()
    if not comic:
        raise HTTPException(status_code=404, detail="Comic not found")
    out = ComicOut.model_validate(comic)
    if comic.session_id:
        er = db.query(EmotionResult).filter(EmotionResult.session_id == comic.session_id).first()
        if er:
            out.emotion = er.final_emotion.value
    return out


@router.post("/ratings", response_model=RatingOut, status_code=status.HTTP_201_CREATED)
def submit_rating(body: RatingCreate, current_user: StandardUser, db: Session = Depends(get_db)):
    comic = db.query(Comic).filter(
        Comic.id == body.comic_id, Comic.user_id == current_user.id
    ).first()
    if not comic:
        raise HTTPException(status_code=404, detail="Comic not found")
    rating = Rating(
        comic_id=body.comic_id,
        user_id=current_user.id,
        stars=body.stars,
        feedback=body.feedback,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating
