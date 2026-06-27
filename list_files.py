import os

repo_root = "."
for root, dirs, files in os.walk(repo_root):
    # Skip hidden folders like .git
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for file in files:
        file_path = os.path.join(root, file)
        print(file_path)
