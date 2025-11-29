from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from src.webapp.models.bag import Bag


def get_bag(db: Session, bag_id: int) -> Optional[Bag]:
    return db.query(Bag).filter(Bag.id == bag_id).first()


def get_bag_by_tg_id(db: Session, tg_id: int) -> Optional[Bag]:
    """Вернуть текущую сумку юзера (если логика одна сумка на юзера)."""
    return (
        db.query(Bag)
        .filter(Bag.tg_id == tg_id)
        .order_by(Bag.last_updated.desc())
        .first()
    )


def list_bags_by_tg_id(db: Session, tg_id: int) -> Sequence[Bag]:
    return (
        db.query(Bag)
        .filter(Bag.tg_id == tg_id)
        .order_by(Bag.last_updated.desc())
        .all()
    )


def create_bag(db: Session, tg_id: int, **extra_fields) -> Bag:
    """
    Создать новую Bag для пользователя.
    extra_fields — любые дополнительные поля модели Bag (meta, status и т.п.).
    """
    now = datetime.utcnow()
    bag = Bag(
        tg_id=tg_id,
        last_updated=now,
        **extra_fields,
    )
    db.add(bag)
    db.commit()
    db.refresh(bag)
    return bag


def update_bag(db: Session, bag: Bag, **fields) -> Bag:
    """
    Обновить поля Bag. fields может содержать любые валидные атрибуты модели.
    """
    for key, value in fields.items():
        setattr(bag, key, value)
    bag.last_updated = datetime.utcnow()
    db.add(bag)
    db.commit()
    db.refresh(bag)
    return bag


def delete_bag(db: Session, bag: Bag) -> None:
    db.delete(bag)
    db.commit()

