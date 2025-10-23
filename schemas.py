from pydantic import BaseModel

class FileInfo(BaseModel):
    directories: list[str]
    files: list[str]
