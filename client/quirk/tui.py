import sys
from questionary import Style

tool_actions = {
    "get_file_info": "Scanning Files",
    "read_file": "Reading File Contents",
    "write_file": "Writing.",
    "delete_path": "Deleting..",
    "copy_file": "Copying File..",
    "run_file": "Executing Script..",
    "create_file": "Creating file.",
    "create_directory": "Creating folder",
    "rename_path": "Renaming path..",
    "run_shell_command": "Running command",
    "_default": "Quirking",
}

quirk_style = Style(
    [
        ("qmark",       "fg:#5fafff bold"),
        ("question",    "fg:#ffffff bold"),
        ("answer",      "fg:#aaffaa bold"),
        ("pointer",     "fg:#ffaf5f bold"),
        ("highlighted", "fg:#ffaf5f bold"),
        ("selected",    "fg:#5fffff bold"),
        ("separator",   "fg:#444444"),
        ("instruction", "fg:#888888 italic"),
        ("text",        "fg:#cccccc"),
        ("disabled",    "fg:#555555 italic"),
    ]
)

glitch = ["Decoding", "Working", "Thinking", "Quirking", "Analyzing"]

def banner() -> None:
    title = "Quirk"
    line = "─" * (len(title) + 8)
    print(f"\n\033[38;5;180m{line}\033[0m")
    print(f"\033[1m\033[38;5;179m   {title}   \033[0m")
    print(f"\033[38;5;180m{line}\033[0m\n")

def print_agent(msg: str, color: str = "", end: str="\n") -> None:
    prefix = "" 
    reset = "\033[0m"

    if color == "quirk":
        msg_color = "\033[1m\033[38;5;153m"
    elif color == "green":
        msg_color = "\033[38;5;140m"
    elif color == "yellow":
        msg_color = "\033[38;5;228m"
    elif color == "gray":
        msg_color = "\033[38;5;244m"
    elif color == "text":
        msg_color = "\033[38;5;254m"
    else:
        msg_color = "\033[38;5;252m"

    if end == "\n":
        print(f"{prefix}{msg_color}{msg}{reset}", end=end)
    
    else:
        sys.stdout.write(f"{msg_color}{msg}{reset}")
        sys.stdout.flush()

