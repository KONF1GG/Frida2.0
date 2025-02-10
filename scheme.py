from pydantic import BaseModel

class Page(BaseModel):
    title: str
    text: str
    book_name: str
    book_slug: str
    page_slug: str

class VectorWikiData(BaseModel):
    hash: str
    text: str
    textTitleLess: str