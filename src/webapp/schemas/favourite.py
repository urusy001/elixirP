from pydantic import BaseModel, ConfigDict


class FavouriteBase(BaseModel):
    onec_id: str
    user_id: int  # на базовом уровне во всех схемах


class FavouriteCreate(FavouriteBase):
    """То, что приходит от клиента при добавлении в избранное."""
    pass


class FavouriteDelete(FavouriteBase):
    """Можно использовать в DELETE, если захотелось body, а не query."""
    pass


class FavouriteOut(FavouriteBase):
    """То, что мы возвращаем клиенту."""
    id: int

    model_config = ConfigDict(from_attributes=True)