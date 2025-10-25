import os

root_dir = os.getcwd()

def get_working_directory():
    working_directory = os.path.abspath(os.path.join(root_dir, "testing_directory"))
    os.makedirs(working_directory, exist_ok=True)
    return working_directory

