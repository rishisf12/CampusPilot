from sqlmodel import SQLModel, Field


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    subject: str
    body: str
