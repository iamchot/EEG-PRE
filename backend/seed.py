#!/usr/bin/env python
"""
Quick database seed script.
Creates admin user and verifies database connection.
Run: python seed.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, Base, engine
from app.models.user import User, Role
from app.services.auth_service import hash_password


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
    finally:
        db.close()

    print("Done!")


if __name__ == "__main__":
    main()
