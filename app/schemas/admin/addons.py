from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AddOnBase(BaseModel):
    name: str
    description: str
    price: float
    category: str


class AddOnCreate(AddOnBase):
    pass


class AddOnResponse(AddOnBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)

