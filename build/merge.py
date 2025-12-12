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

def merge_files(sorted_modules, module_to_file, source_dir: Path, output_file: Path):
    """Merge files in order, stripping local imports."""
    processed_modules = set(sorted_modules)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as out:
        out.write("# AUTO-GENERATED FILE. DO NOT EDIT MANUALLY.\n")
        out.write(f"# Source: {source_dir}\n\n")

        for module in sorted_modules:
            rel_path = module_to_file[module]
            full_path = source_dir / rel_path
            
            out.write(f"\n# --- MODULE: {module} ({rel_path}) ---\n")
            
            lines = full_path.read_text(encoding="utf-8").splitlines(keepends=True)
            
            for line in lines:
                stripped = line.strip()
                should_skip = False
                
                if stripped.startswith("import ") or stripped.startswith("from "):
                    try:
                        node = ast.parse(stripped).body[0]
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name.split('.')[0] in processed_modules:
                                    should_skip = True
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and node.module.split('.')[0] in processed_modules:
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