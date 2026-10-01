from pydantic import BaseModel, ConfigDict


class ItemIn(BaseModel):
    title: str
    body: str = ""


class ItemOut(ItemIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
