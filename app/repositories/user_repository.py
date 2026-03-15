from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def create(self, db: Session, *, email: str, password_hash: str) -> User:
        user = User(email=email.strip(), password_hash=password_hash)
        db.add(user)
        db.flush()
        return user

    def get_by_email(self, db: Session, email: str) -> User | None:
        normalized = email.strip().lower()
        stmt = select(User).where(func.lower(User.email) == normalized)
        return db.scalar(stmt)

    def get_by_id(self, db: Session, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return db.scalar(stmt)
