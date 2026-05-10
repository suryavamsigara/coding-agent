from pathlib import Path

def get_working_directory() -> Path:
    return Path.cwd()