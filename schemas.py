from pydantic import BaseModel

class FileInfo(BaseModel):
    directories: list[str]
    files: list[str]

class ReadSuccess(BaseModel):
    content: str

class ReadError(BaseModel):
    error: str
    