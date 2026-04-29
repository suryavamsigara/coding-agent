import subprocess
import shlex
from pathlib import Path
from tenet.config import get_working_directory

def run_shell_command(command: str):
    """
    Execute a shell command within the working directory.
    """
    base_dir: Path = get_working_directory()

    if "sudo" in command or "rm -rf /" in command:
        return f"Error: Cannot execute this command."
    
    try:
        args = shlex.split(command)

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=base_dir,
            timeout=60
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {e}"
