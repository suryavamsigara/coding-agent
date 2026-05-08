import os
import subprocess

from tenet.config import get_working_directory

# Commands that are explicitly blocked regardless of context
BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf ~", "mkfs", "dd if=", "> /dev/sda",
    "shutdown", "reboot", "halt", "poweroff",
}

ALLOWED_PREFIXES = (
    "python", "python3", "pip", "pip3",
    "node", "npm", "npx", "yarn", "pnpm",
    "git",
    "cargo", "rustc",
    "go ",
    "make", "cmake",
    "ls", "cat", "echo", "pwd", "find", "grep", "rg", "awk", "sed",
    "head", "tail", "wc", "sort", "uniq", "diff", "patch",
    "curl", "wget",
    "pytest", "mypy", "ruff", "black", "isort", "flake8",
    "tsc", "eslint", "prettier",
    "docker", "docker-compose",
    "bash -c", "sh -c",
    "env", "which", "type",
)

DEFAULT_TIMEOUT = 60  # seconds


def run_command(
    command: str,
    working_dir: str = ".",
    timeout: int = DEFAULT_TIMEOUT,
    env_vars: dict = None,
) -> dict:
    # Safety: block destructive commands
    cmd_lower = command.strip().lower()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return {
                "command": command,
                "stdout": "",
                "stderr": f"Command blocked for safety: contains '{blocked}'",
                "exit_code": -1,
                "success": False,
                "timed_out": False,
            }

    # Safety: allowlist check
    if not any(cmd_lower.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return {
            "command": command,
            "stdout": "",
            "stderr": (
                f"Command not in allowed list. Allowed prefixes: "
                + ", ".join(sorted(ALLOWED_PREFIXES))
            ),
            "exit_code": -1,
            "success": False,
            "timed_out": False,
        }

    base_dir = get_working_directory().resolve()

    if working_dir != ".":
        run_dir = (base_dir / working_dir).resolve()
        try:
            run_dir.relative_to(base_dir)
        except Exception:
            return {
                "command": command,
                "stdout": "",
                "stderr": f"working_dir '{working_dir}' is outside the project root.",
                "exit_code": -1,
                "success": False,
                "timed_out": False,
            }
    else:
        run_dir = base_dir

    env = {**os.environ}
    if env_vars:
        env.update(env_vars)

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "command": command,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "exit_code": proc.returncode,
            "success": proc.returncode == 0,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s.",
            "exit_code": -1,
            "success": False,
            "timed_out": True,
        }
    except Exception as e:
        return {
            "command": command,
            "stdout": "",
            "stderr": f"Execution error: {e}",
            "exit_code": -1,
            "success": False,
            "timed_out": False,
        }