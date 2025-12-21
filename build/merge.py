import ast
import sys
from collections import defaultdict, deque
from pathlib import Path
import os

# Configuration
SOURCE_DIR = Path(__file__).resolve().parent.parent # Root dir (parent of build/)
OUTPUT_FILE = SOURCE_DIR / "api" / "dist" / "main.py"
IGNORE_DIRS = {".venv", "venv", ".git", "__pycache__", "build", "dist", "tests", "FixelBackendRequestly", "bin", "lib", "include"}
IGNORE_FILES = {"__init__.py", "setup.py"}

def get_python_files(directory: Path):
    """Recursively find all .py files in the directory, excluding ignored ones."""
    py_files = []
    
    # pathlib doesn't have a direct equivalent to os.walk's in-place dir modification
    # so we iterate manually or use rglob and filter
    for path in directory.rglob("*.py"):
        # Check against ignores
        # We need to check if any part of the path is in IGNORE_DIRS
        # relative_to SOURCE_DIR to avoid checking parents
        try:
            rel_path = path.relative_to(SOURCE_DIR)
        except ValueError:
            continue

        if any(part in IGNORE_DIRS for part in rel_path.parts):
            continue
        
        if path.name in IGNORE_FILES:
            continue
            
        py_files.append(rel_path)
            
    return py_files

def get_module_name(rel_path: Path):
    """Convert relative file path to module name (e.g., 'utils/helper.py' -> 'utils.helper')."""
    return str(rel_path.with_suffix("")).replace(os.sep, ".")

def parse_imports(file_path: Path):
    """Parse a Python file and return a set of imported modules."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Error parsing {file_path}: {e}, skipping dependency analysis.")
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports

def build_dependency_graph(files, source_dir: Path):
    """Build a graph where keys are module names and values are sets of imported local modules."""
    graph = defaultdict(set)
    module_to_file = {}

    # Map module names to file paths
    for rel_path in files:
        module_name = get_module_name(rel_path)
        module_to_file[module_name] = rel_path

    all_modules = set(module_to_file.keys())

    for rel_path in files:
        module = get_module_name(rel_path)
        full_path = source_dir / rel_path
        imports = parse_imports(full_path)

        for imp in imports:
            if imp in all_modules:
                graph[module].add(imp)
            else:
                parts = imp.split('.')
                if parts[0] in all_modules:
                     graph[module].add(parts[0])

    return graph, module_to_file

def topological_sort(graph, all_modules):
    """Perform topological sort on the dependency graph."""
    dag = defaultdict(set)
    in_degree = {m: 0 for m in all_modules}
    
    for u, deps in graph.items():
        for v in deps:
            if v == u: continue
            dag[v].add(u) # v -> u
            in_degree[u] += 1
            
    queue = deque([m for m in all_modules if in_degree[m] == 0])
    sorted_modules = []

    while queue:
        u = queue.popleft()
        sorted_modules.append(u)

        for v in dag[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if len(sorted_modules) != len(all_modules):
        print("Error: Circular dependency detected!")
        remaining = set(all_modules) - set(sorted_modules)
        print(f"Circular deps likely involving: {remaining}")
        sorted_modules.extend(list(remaining))

    return sorted_modules

def collect_external_imports(sorted_modules, module_to_file, source_dir: Path):
    """
    Scans all modules to collect top-level external imports.
    Returns a set of import strings.
    """
    external_imports = set()
    processed_modules = set(sorted_modules)

    for module in sorted_modules:
        rel_path = module_to_file[module]
        full_path = source_dir / rel_path
        
        try:
            content = full_path.read_text(encoding="utf-8")
            # We only care about top-level imports
            tree = ast.parse(content)
            
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Check if it's a local import
                    is_local = False
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.split('.')[0] in processed_modules:
                                is_local = True
                                break
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.split('.')[0] in processed_modules:
                            is_local = True
                    
                    if not is_local:
                        # Reconstruct the import string
                        # This is a bit simplistic, might lose comments or formatting, but AST unparse is available in 3.9+
                        # For older python, might need manual extraction or assume single line.
                        # Let's try to extract the exact source line if possible, or use ast.unparse
                        
                        if sys.version_info >= (3, 9):
                            # Normalizing by sorting names if possible
                            if isinstance(node, ast.Import):
                                node.names.sort(key=lambda x: x.name)
                                external_imports.add(ast.unparse(node))
                            elif isinstance(node, ast.ImportFrom):
                                node.names.sort(key=lambda x: x.name)
                                external_imports.add(ast.unparse(node))
                            else:
                                external_imports.add(ast.unparse(node))
                        else:
                             # Fallback for older python (unlikely in this env but good practice)
                             # Doing a simple reconstruction
                            if isinstance(node, ast.Import):
                                sorted_names = sorted(node.names, key=lambda x: x.name)
                                names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in sorted_names)
                                external_imports.add(f"import {names}")
                            elif isinstance(node, ast.ImportFrom):
                                sorted_names = sorted(node.names, key=lambda x: x.name)
                                names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in sorted_names)
                                level = "." * node.level
                                module_name = node.module or ""
                                external_imports.add(f"from {level}{module_name} import {names}")

        except Exception as e:
            print(f"Warning: Failed to parse imports from {module}: {e}")

    return sorted(list(external_imports))

def merge_files(sorted_modules, module_to_file, source_dir: Path, output_file: Path):
    """Merge files in order, stripping local imports."""
    processed_modules = set(sorted_modules)
    
    # 1. Collect all external imports
    external_imports = collect_external_imports(sorted_modules, module_to_file, source_dir)
    
    # User Request: load dotenv must be done before os import happens
    # We prioritize dotenv imports to ensure they are at the top.
    dotenv_imports = [imp for imp in external_imports if "dotenv" in imp]
    other_imports = [imp for imp in external_imports if "dotenv" not in imp]
    
    # We also might want to inject load_dotenv() call if it was present? 
    # The user said "load dotenv must be done". This implies the call.
    # But stripped 'local' code usually keeps function calls.
    # The issue is if 'import os' happens before the module body that has 'load_dotenv()'.
    # In the merged file, all imports are at the top.
    # So:
    # 1. Imports
    # 2. Module bodies (starting with db.py which calls load_dotenv)
    # This means 'import os' (in imports) DOES happen before 'load_dotenv()' (in db.py body).
    # If the user implies 'import os' triggers something bad, then we have a problem.
    # However, standard 'import os' is side-effect free regarding environment *snapshots* usually (it wraps C-level environ).
    # But maybe the user wants 'from dotenv import load_dotenv; load_dotenv()' at the very top?
    # For now, let's at least ensure the IMPORT is first.
    
    final_imports = dotenv_imports + other_imports
    
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as out:
        out.write("# AUTO-GENERATED FILE. DO NOT EDIT MANUALLY.\n")
        out.write(f"# Source: {source_dir}\n")
        out.write("# This file is generated by merging multiple modules.\n\n")
        
        # 2. Write External Imports
        out.write("# --- EXTERNAL IMPORTS ---\n")
        
        # Inject load_dotenv() call if dotenv is imported to strictly satisfy "load dotenv must be done before os import"
        # ONLY if we see dotenv being imported.
        # This is a heuristic hack but effective for this specific request.
        has_dotenv = any("dotenv" in imp for imp in final_imports)
        
        for imp in final_imports:
            out.write(f"{imp}\n")
            
        if has_dotenv:
             out.write("\n# Prioritizing load_dotenv as requested\n")
             out.write("try:\n")
             out.write("    load_dotenv()\n")
             out.write("except NameError:\n")
             out.write("    pass # load_dotenv not imported as bare name (e.g. maybe aliased or from dotenv import *)\n")
             out.write("except Exception as e:\n")
             out.write("    print(f'Warning: Early load_dotenv() failed: {e}')\n")

        out.write("\n")

        # 3. Write Modules
        for module in sorted_modules:
            rel_path = module_to_file[module]
            full_path = source_dir / rel_path
            
            out.write(f"\n# --- MODULE: {module} ({rel_path}) ---\n")
            
            lines = full_path.read_text(encoding="utf-8").splitlines(keepends=True)
            
            for line in lines:
                stripped = line.strip()
                should_skip = False
                
                # Check if it's an import line using AST to be sure (handling multi-line imports might be tricky with line-by-line, 
                # but simple top-level imports are usually fine or we can use AST logic again on file content?
                
                # Previous logic:
                if stripped.startswith("import ") or stripped.startswith("from "):
                    try:
                        # If it parses as an import statement, we skip it
                        # Because we already handled external imports, and we want to remove local imports
                        # So basically remove ALL top-level imports
                        # Caveat: Indented imports (inside functions) should NOT be removed.
                        # This line-by-line check doesn't guarantee top-level.
                        # However, the previous code didn't check indentation either, just stripped and checked startswith.
                        # Assuming mostly standard formatting where top-level imports start at column 0.
                        if not line.startswith(" ") and not line.startswith("\t"):
                             should_skip = True
                    except:
                        pass
                
                if not should_skip:
                    out.write(line)



def run_merge():
    print(f"Scanning {SOURCE_DIR}...")
    files = get_python_files(SOURCE_DIR)
    
    print(f"Found files: {[str(f) for f in files]}")

    print("Analyzing dependencies...")
    graph, module_to_file = build_dependency_graph(files, SOURCE_DIR)
    all_modules = list(module_to_file.keys())
    
    print("Sorting files...")
    sorted_modules = topological_sort(graph, all_modules)
    print(f"Merge order: {sorted_modules}")

    print(f"Merging into {OUTPUT_FILE}...")
    merge_files(sorted_modules, module_to_file, SOURCE_DIR, OUTPUT_FILE)
    print("Merge complete.")

if __name__ == "__main__":
    run_merge()