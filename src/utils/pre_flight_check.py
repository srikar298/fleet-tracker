import os
import sys
import ast
import importlib.util
from typing import Set

def get_imports_from_file(filepath: str) -> Set[str]:
    """Parses a python file and returns all top-level imports."""
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
        except Exception as e:
            print(f"⚠️ Could not parse {filepath}: {e}")
            return set()
            
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.add(name.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports

def check_dependencies() -> bool:
    print("Starting Pre-Flight Dependency Check...\n")
    
    # 1. Gather all imports from src
    all_imports = set()
    src_dir = os.path.join(os.getcwd(), "src")
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                all_imports.update(get_imports_from_file(filepath))

    # 2. Filter out standard libraries and internal modules
    # We can detect internal by checking if the folder exists in src
    internal_modules = {d for d in os.listdir(src_dir) if os.path.isdir(os.path.join(src_dir, d))}
    internal_modules.add("core")
    internal_modules.add("services")
    internal_modules.add("handlers")
    internal_modules.add("utils")
    
    external_imports = {m for m in all_imports if m not in internal_modules}
    
    # 3. Check requirements.txt
    req_file = os.path.join(os.getcwd(), "requirements.txt")
    with open(req_file, 'r') as f:
        reqs = f.read().lower()

    # Mapping common imports to package names
    pkg_map = {
        "PIL": "pillow",
        "telegram": "python-telegram-bot",
        "google": "google-api-python-client",
        "boto3": "boto3",
        "gspread": "gspread",
        "dotenv": "python-dotenv",
        "pydantic": "pydantic",
        "apscheduler": "apscheduler"
    }

    failed = False
    std_libs = {
        "os", "sys", "datetime", "uuid", "typing", "json", "logging", "asyncio", 
        "ast", "importlib", "re", "math", "time", "abc", "csv", "io", "shutil", 
        "warnings", "zipfile", "collections", "hashlib", "hmac", "base64", 
        "functools", "inspect", "pathlib", "random", "string", "traceback"
    }

    print("Dependency Status:")
    for mod in sorted(external_imports):
        if mod in std_libs:
            continue
            
        pkg_name = pkg_map.get(mod, mod).lower()
        
        # Special check for composite packages
        is_present = pkg_name in reqs
        if mod == "googleapiclient" and "google-api-python-client" in reqs:
            is_present = True
        if mod == "botocore" and "boto3" in reqs:
            is_present = True
            
        if not is_present:
            print(f"FAILED in requirements.txt: '{mod}' (expected package: {pkg_name})")
            failed = True
        else:
            print(f"PASSED: {mod}")

    if failed:
        print("\nDEPLOYMENT BLOCKED: Missing dependencies detected!")
        return False
    else:
        print("\nALL SYSTEMS GO: Ready for deployment.")
        return True

if __name__ == "__main__":
    if not check_dependencies():
        sys.exit(1)
