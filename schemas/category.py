from pydantic import BaseModel

class CategorySchema(BaseModel):
    category_name: str
