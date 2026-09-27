#!/usr/bin/env python
"""
Quick database seed script.
Creates admin user and verifies database connection.
Run: python seed.py
"""

import sys
import os
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, Base, engine
from app.models.user import User, Role
from app.models.dataset_collection import EmotionStimulus, Quadrant, StimulusApprovalState
from app.services.auth_service import hash_password
from app.config import get_settings


DEFAULT_STIMULI = [
    {
        "title": "Relax 1",
        "file_path": "relax/relax.mp4",
        "checksum": "6a8c00de9986dbce2463a49ef67687e4d576aaabfe9599a51b5a7daab134fcd3",
        "duration_seconds": 59.95,
        "target_quadrant": Quadrant.positive_low,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Relax 2",
        "file_path": "relax/relax1.mp4",
        "checksum": "7bac4d899130dc77fa4f8a1d2f8f182e9fe5166b6254b981f9d43b52afaed0b6",
        "duration_seconds": 59.86,
        "target_quadrant": Quadrant.positive_low,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Relax 3",
        "file_path": "relax/relax2.mp4",
        "checksum": "ec879e30c67c4db177d16eed56020c097d42ad343f4afac966b978136fd5d32c",
        "duration_seconds": 59.63,
        "target_quadrant": Quadrant.positive_low,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Excited 1",
        "file_path": "excited/excited.mp4",
        "checksum": "ef233118520e56b52ea57f101d4671d0d5e1d84768e54b3989dcf27cc453aa67",
        "duration_seconds": 59.16,
        "target_quadrant": Quadrant.positive_high,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Excited 2",
        "file_path": "excited/excited1.mp4",
        "checksum": "e37b5ac3fa4ad74c3c2b7c412143b05e12f661f9b63dd5b0bd0511ede47a3003",
        "duration_seconds": 59.72,
        "target_quadrant": Quadrant.positive_high,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Excited 3",
        "file_path": "excited/excited2.mp4",
        "checksum": "41ee6e99ef92ef9588636542259fb1487a26fc1dd160c463d39f818133e1d172",
        "duration_seconds": 59.77,
        "target_quadrant": Quadrant.positive_high,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Sad 1",
        "file_path": "sad/sad.mp4",
        "checksum": "4c17d0ffcffafc80bd3d849c61cf2f91fed07e8f759458fd0b402cfce38090b0",
        "duration_seconds": 50.18,
        "target_quadrant": Quadrant.negative_low,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Sad 2",
        "file_path": "sad/sad1.mp4",
        "checksum": "57a6316b264d87ace0402332f86537df9bc1245292ea1d0e908585fb545ce395",
        "duration_seconds": 59.83,
        "target_quadrant": Quadrant.negative_low,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Sad 3",
        "file_path": "sad/sad2.mp4",
        "checksum": "68d7b1bc906c501e11441077b77dd7e984489ae87aaeaefd7aada8a11b4beea1",
        "duration_seconds": 59.58,
        "target_quadrant": Quadrant.negative_low,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Stress 1",
        "file_path": "stress/stress1.mp4",
        "checksum": "c7b95a577a2d1dbcf1b3d6c35c89f11dbe0c09afe525e50e23a5a3a5f0b127fc",
        "duration_seconds": 50.0,
        "target_quadrant": Quadrant.negative_high,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Stress 2",
        "file_path": "stress/stress2.mp4",
        "checksum": "215ef31178248da6f6da9ff68b7c5e8b003a08c55ca22aa83cab8ec089b35901",
        "duration_seconds": 59.72,
        "target_quadrant": Quadrant.negative_high,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
    {
        "title": "Stress 3",
        "file_path": "stress/stress3.mp4",
        "checksum": "833aa2abd5c1d8d7b9792ae49885ce2b536b33b4c9ca30b9b3126255da94bc96",
        "duration_seconds": 59.7,
        "target_quadrant": Quadrant.negative_high,
        "approval_state": StimulusApprovalState.approved,
        "stimulus_set_version": "v1.0",
    },
]


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def seed_stimuli(db):
    print("Seeding/updating emotion stimuli...")
    stimuli_root = Path(get_settings().collection_stimulus_dir).resolve()
    for item in DEFAULT_STIMULI:
        # Check if file exists on disk to sync actual sha256
        rel_path = Path(item["file_path"])
        file_on_disk = stimuli_root / rel_path
        checksum = item["checksum"]
        if file_on_disk.is_file():
            checksum = compute_file_sha256(file_on_disk)

        existing = (
            db.query(EmotionStimulus)
            .filter(
                (EmotionStimulus.file_path == item["file_path"])
                | (EmotionStimulus.title == item["title"])
            )
            .first()
        )
        if existing:
            updated = False
            if existing.checksum != checksum:
                print(f"  Updating checksum for {existing.title}: {existing.checksum[:16]}... -> {checksum[:16]}...")
                existing.checksum = checksum
                updated = True
            if existing.duration_seconds != item["duration_seconds"]:
                existing.duration_seconds = item["duration_seconds"]
                updated = True
            if existing.target_quadrant != item["target_quadrant"]:
                existing.target_quadrant = item["target_quadrant"]
                updated = True
            if existing.approval_state != item["approval_state"]:
                existing.approval_state = item["approval_state"]
                updated = True
            if updated:
                db.commit()
                print(f"  Stimulus '{existing.title}' updated.")
        else:
            stim = EmotionStimulus(
                title=item["title"],
                file_path=item["file_path"],
                checksum=checksum,
                duration_seconds=item["duration_seconds"],
                target_quadrant=item["target_quadrant"],
                approval_state=item["approval_state"],
                stimulus_set_version=item["stimulus_set_version"],
            )
            db.add(stim)
            db.commit()
            print(f"  Stimulus '{stim.title}' created with checksum {checksum[:16]}...")

    print("Emotion stimuli synchronized.")


def main():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Ensure roles
        for name in ("user", "admin"):
            if not db.query(Role).filter(Role.name == name).first():
                db.add(Role(name=name))
        db.commit()
        print("Roles seeded.")

        # Create admin user if not exists
        admin_email = "admin@dreamcomic.local"
        if not db.query(User).filter(User.email == admin_email).first():
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            admin = User(
                username="admin",
                email=admin_email,
                password_hash=hash_password("Admin1234!"),
                role_id=admin_role.id,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"Admin user created: {admin_email} / Admin1234!")
        else:
            print("Admin user already exists.")

        # Seed and sync emotion stimuli
        seed_stimuli(db)

    finally:
        db.close()

    print("Done!")


if __name__ == "__main__":
    main()
