import os
import schemas

working_directory = "testing_directory"
print(os.path.abspath(working_directory))

def get_file_info(working_directory: str, directory: str = ".") -> schemas.FileInfo | str:
    try:
        absolute_working_directory = os.path.abspath(working_directory)
        absolute_directory = os.path.abspath(os.path.join(absolute_working_directory, directory))

        if not os.path.isdir(absolute_directory):
            return f"Error: Directory {absolute_directory} does not exist"

        if not absolute_directory.startswith(absolute_working_directory):
            return f"Error: Directory '{absolute_directory}' is not in working directory."
        
        file_paths = []
        dir_paths = []
        
        for root, dirs, files in os.walk(absolute_directory):
            relative_root = os.path.relpath(root, absolute_directory)

            for file in files:
                if relative_root == ".":
                    file_paths.append(file)
                else:
                    file_paths.append(os.path.join(relative_root, file))
            
            for dir_name in dirs:
                if relative_root == ".":
                    dir_paths.append(dir_name)
                else:
                    dir_paths.append(os.path.join(relative_root, dir_name))

        return schemas.FileInfo(directories=dir_paths, files=file_paths)
    except Exception as e:
        return f"Error: Could not access the files: {e}"
print("function is being called...")
result = get_file_info(working_directory)
if isinstance(result, schemas.FileInfo):
    print(result.model_dump())
print("function finished...")
