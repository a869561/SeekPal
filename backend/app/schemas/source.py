from pydantic import BaseModel, Field


class AddSourceRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)


class SettingsPatch(BaseModel):
    theme: str | None = None
    fontSize: str | None = None
    language: str | None = None
