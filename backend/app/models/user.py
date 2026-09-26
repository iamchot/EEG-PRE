from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสบทบาทสิทธิ์ (Primary Key)")
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="ชื่อบทบาท เช่น user, admin")

    users: Mapped[list[User]] = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสผู้ใช้ (Primary Key)")
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True, comment="ชื่อบัญชีผู้ใช้สำหรับล็อกอิน")
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True, comment="อีเมลผู้ใช้งาน")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="รหัสผ่านที่เข้ารหัสความปลอดภัยด้วย bcrypt")
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False, default=1, comment="สิทธิ์การใช้งาน (FK -> roles.id)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="สถานะเปิดใช้งานบัญชี (1=ใช้งานได้, 0=ถูกระงับ)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="วันที่ลงทะเบียน")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="วันที่แก้ไขข้อมูลล่าสุด")

    role: Mapped[Role] = relationship("Role", back_populates="users")
    personas: Mapped[list["Persona"]] = relationship("Persona", back_populates="user", cascade="all, delete-orphan")
    comics: Mapped[list["Comic"]] = relationship("Comic", back_populates="user")
    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="user")
