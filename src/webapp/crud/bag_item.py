from typing import Optional, Sequence
from sqlalchemy.orm import Session

from src.webapp.models import BagItem


def get_bag_item(db: Session, item_id: int) -> Optional[BagItem]:
    return db.query(BagItem).filter(BagItem.id == item_id).first()


def list_bag_items(db: Session, bag_id: int) -> Sequence[BagItem]:
    return (
        db.query(BagItem)
        .filter(BagItem.bag_id == bag_id)
        .order_by(BagItem.id.asc())
        .all()
    )


def create_bag_item(
        db: Session,
        bag_id: int,
        quantity: int,
        **extra_fields,
) -> BagItem:
    """
    Создать BagItem внутри конкретной Bag.
    extra_fields — любые доп. поля: product_id, price, total и т.п.
    """
    item = BagItem(
        bag_id=bag_id,
        quantity=quantity,
        **extra_fields,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_bag_item(db: Session, item: BagItem, **fields) -> BagItem:
    """
    Обновить BagItem. Например, quantity, total и т.п.
    """
    for key, value in fields.items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_bag_item(db: Session, item: BagItem) -> None:
    db.delete(item)
    db.commit()


def delete_bag_items_by_bag(db: Session, bag_id: int) -> int:
    """
    Удалить все BagItem для конкретной Bag.
    Возвращает количество удалённых записей.
    """
    q = db.query(BagItem).filter(BagItem.bag_id == bag_id)
    deleted = q.delete(synchronize_session=False)
    db.commit()
    return deleted
