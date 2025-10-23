from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert
from typing import List, Optional, Any

from ..models import Feature, Product
from ..schemas import FeatureCreate, FeatureUpdate


async def create_feature(db: AsyncSession, feature: FeatureCreate) -> Feature | None:
    """
    Creates or updates a feature.
    Silently skips if product_onec_id is missing or not found.
    Never raises, never aborts the sync.
    """
    try:
        # 🧩 1️⃣ Check that feature has a valid product_onec_id
        if not feature.product_onec_id:
            print(f"⚠️ Skipping feature '{feature.name}' — no product_onec_id provided")
            return None

        # 🧩 2️⃣ Check that referenced product exists in DB
        exists = await db.scalar(
            select(Product.id).filter_by(onec_id=feature.product_onec_id)
        )
        if not exists:
            print(f"⚠️ Skipping feature '{feature.name}' — product not found: {feature.product_onec_id}")
            return None

        # 🧩 3️⃣ Build base insert statement
        base_insert = insert(Feature).values(**feature.dict())

        # 🧩 4️⃣ Add ON CONFLICT clause referencing the base insert
        stmt = base_insert.on_conflict_do_update(
            index_elements=["onec_id"],
            set_={
                "name": base_insert.excluded.name,
                "code": base_insert.excluded.code,
                "product_onec_id": base_insert.excluded.product_onec_id,
                "file_id": base_insert.excluded.file_id,
                "price": base_insert.excluded.price,
                "balance": base_insert.excluded.balance,
            },
        ).returning(Feature)

        # 🧩 5️⃣ Execute safely
        result = await db.execute(stmt)
        await db.commit()

        created = result.scalar_one_or_none()
        if created:
            print(f"✅ Synced feature '{feature.name}' for product {feature.product_onec_id}")
        return created

    except IntegrityError:
        await db.rollback()
        return None

async def get_features(db: AsyncSession) -> List[Feature]:
    result = await db.execute(select(Feature))
    return result.scalars().all()

async def get_feature(db: AsyncSession, attr_name: str, value: Any) -> Optional[Feature]:
    if not hasattr(Feature, attr_name):
        raise AttributeError(f"Feature has no attribute '{attr_name}'")
    column = getattr(Feature, attr_name)
    result = await db.execute(select(Feature).where(column == value))
    return result.scalars().first()

async def update_feature(db: AsyncSession, feature_id: int, feature_data: FeatureUpdate) -> Optional[Feature]:
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    db_feature = result.scalars().first()
    if db_feature is None:
        return None

    for field, value in feature_data.dict().items():
        setattr(db_feature, field, value)

    db.add(db_feature)
    await db.commit()
    await db.refresh(db_feature)
    return db_feature