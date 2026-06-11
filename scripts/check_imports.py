import os
import sys
import importlib.util
import ast

def check_imports_in_file(filepath):
    with open(filepath, 'r') as f:
        try:
            tree = ast.parse(f.read())
        except Exception as e:
            return [f"Error parsing {filepath}: {e}"]

    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                check_import(name.name, filepath, errors)
        elif isinstance(node, ast.ImportFrom):
            check_import(node.module, filepath, errors)
    return errors

def check_import(module_name, from_file, errors):
    if not module_name: return
    # Skip standard library and installed packages for now, focus on local app
    if module_name.startswith('app.') or module_name == 'app':
        # Convert app.foo.bar to app/foo/bar.py or app/foo/bar/__init__.py
        parts = module_name.split('.')
        path = os.path.join(*parts)
        if not (os.path.exists(path + '.py') or os.path.exists(os.path.join(path, '__init__.py'))):
            errors.append(f"Broken local import '{module_name}' in {from_file}")
    else:
        # Check if it can be found in sys.path
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            # Special case for moviepy v2 subimports if any
            errors.append(f"Missing external import '{module_name}' in {from_file}")

def main():
    all_errors = []
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                all_errors.extend(check_imports_in_file(path))

    if all_errors:
        print("\n".join(all_errors))
    else:
        print("No broken imports found in 'app/'")

if __name__ == "__main__":
    main()
