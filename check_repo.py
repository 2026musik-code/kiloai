import os

print("=== Struktur Repository ===")
for root, dirs, files in os.walk("."):
    # Skip .git folder
    if ".git" in dirs:
        dirs.remove(".git")
    level = root.replace(".", "").count(os.sep)
    indent = " " * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = " " * 2 * (level + 1)
    for file in files:
        print(f"{subindent}{file}")
