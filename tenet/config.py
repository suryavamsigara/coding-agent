from pathlib import Path

# from pydantic_settings import BaseSettings

# class Settings(BaseSettings):
#     database_hostname: str
#     database_port: str
#     database_password: str
#     database_name: str
#     database_username: str
#     gemini_api_key: str

#     class Config:
#         env_file = ".env"

# settings = Settings()

def get_working_directory() -> Path:
    return Path.cwd()