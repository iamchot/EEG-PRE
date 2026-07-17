from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import StandardUser
from app.models.persona import Persona
from app.schemas.persona import PersonaCreate, PersonaOut, PersonaUpdate

router = APIRouter(prefix="/personas", tags=["personas"])


def _get_own_persona(persona_id: int, user_id: int, db: Session) -> Persona:
    p = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Persona not found")
    return p


@router.get("/", response_model=list[PersonaOut])
def list_personas(current_user: StandardUser, db: Session = Depends(get_db)):
    return db.query(Persona).filter(Persona.user_id == current_user.id).all()


@router.post("/", response_model=PersonaOut, status_code=status.HTTP_201_CREATED)
def create_persona(body: PersonaCreate, current_user: StandardUser, db: Session = Depends(get_db)):
    persona = Persona(user_id=current_user.id, **body.model_dump())
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


@router.get("/{persona_id}", response_model=PersonaOut)
def get_persona(persona_id: int, current_user: StandardUser, db: Session = Depends(get_db)):
    return _get_own_persona(persona_id, current_user.id, db)


@router.patch("/{persona_id}", response_model=PersonaOut)
def update_persona(
    persona_id: int, body: PersonaUpdate, current_user: StandardUser, db: Session = Depends(get_db)
):
    persona = _get_own_persona(persona_id, current_user.id, db)
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(persona, key, value)
    db.commit()
    db.refresh(persona)
    return persona


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_persona(persona_id: int, current_user: StandardUser, db: Session = Depends(get_db)):
    persona = _get_own_persona(persona_id, current_user.id, db)
    db.delete(persona)
    db.commit()
