import os
from schemas import ReadSuccess, ReadError

def read_file(working_directory: str, file_path: str, max_lines: int | None = None) -> ReadSuccess | ReadError:
    try:
        absolute_working_directory = os.path.abspath(working_directory)
        absolute_file_path = os.path.abspath(os.path.join(working_directory, file_path))

        if not absolute_file_path.startswith(absolute_working_directory):
            return ReadError(error=f"File '{file_path}' is not in working directory.")

        if not os.path.isfile(absolute_file_path):
            return ReadError(error=f"Error: '{file_path}' does not exist or is not a file.")

        try:
            with open(absolute_file_path, 'r', encoding='utf-8') as f:
                if max_lines is not None and max_lines > 0:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    file_content = "".join(lines)
                    if i >= max_lines:
                        file_content += f"\n File truncated at {max_lines} lines"
                else:
                    file_content = f.read()
            return ReadSuccess(content=file_content)
    
        except Exception as e:
            return ReadError(error=f"Error: could not read file '{file_path}', details: {e}")
        
    except Exception as e:
            return ReadError(error=f"Error: details: {e}")
        