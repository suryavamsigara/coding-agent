import os

# root_dir = os.getcwd()

def get_working_directory():
    # working_directory = os.path.abspath(os.path.join(root_dir, "testing_directory"))
    # os.makedirs(working_directory, exist_ok=True)
    # return working_directory
    client_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    testing_dir = os.path.join(client_dir, "testing_directory")
    os.makedirs(testing_dir, exist_ok=True)
    return testing_dir
