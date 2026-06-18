import os
import importlib.util
import traceback

def check_imports():
    for root_dir in ['app', 'packages']:
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith('.py') and file != '__init__.py':
                    path = os.path.join(root, file)
                    mod_name = path.replace('/', '.').replace('\\\\', '.')[:-3]
                    try:
                        importlib.import_module(mod_name)
                    except Exception as e:
                        print(f"ERROR in {mod_name}: {e}")
                        
if __name__ == "__main__":
    check_imports()
