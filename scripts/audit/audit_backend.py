import os
import sys
import importlib
import pkgutil
import traceback

def audit_imports(start_dir):
    print(f"Starting import audit in: {start_dir}")
    
    # Add the current directory to sys.path to allow imports like 'backend.xxx'
    sys.path.insert(0, os.getcwd())
    
    error_count = 0
    success_count = 0
    
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file.endswith(".py") and file != "audit_backend.py":
                # Construct module path
                rel_path = os.path.relpath(os.path.join(root, file), os.getcwd())
                module_name = rel_path.replace(os.sep, ".").replace(".py", "")
                
                # Skip __init__ if it's just marking a package (optional, but good to check them too)
                if module_name.endswith(".__init__"):
                    module_name = module_name[:-9]
                
                try:
                    print(f"Checking {module_name}...", end=" ")
                    importlib.import_module(module_name)
                    print("OK")
                    success_count += 1
                except Exception as e:
                    print("FAIL")
                    print(f"Error importing {module_name}:")
                    traceback.print_exc()
                    error_count += 1
                    
    print("-" * 40)
    print(f"Audit complete.")
    print(f"Successful imports: {success_count}")
    print(f"Failed imports: {error_count}")

if __name__ == "__main__":
    audit_imports("backend")
