import subprocess
import shutil
import sys
from pathlib import Path

# Configuration
SOURCE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = SOURCE_DIR / "requirements.txt"

def run_export():
    """Export dependencies from pyproject.toml to requirements.txt using uv."""
    print("Exporting dependencies...")
    
    # Check for 'uv' executable in PATH
    uv_executable = shutil.which("uv")
    
    if uv_executable:
        base_cmd = [uv_executable]
    else:
        # Fallback to running as a python module from the current environment
        print("Note: 'uv' executable not found in PATH. Attempting to use 'python -m uv'...")
        base_cmd = [sys.executable, "-m", "uv"]

    try:
        # Verify uv is callable
        # We use a simple check; if this fails, we bail out.
        # Capturing output to avoid clutter if it works.
        subprocess.run(base_cmd + ["--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: 'uv' is not available in PATH or as a python module.")
        print("Please install it via 'pip install uv' or ensuring it is in your PATH.")
        return False

    try:
        cmd = base_cmd + ["export", "--format", "requirements-txt", "--output-file", str(REQUIREMENTS_FILE)]
        
        # Check if pyproject.toml exists
        if not (SOURCE_DIR / "pyproject.toml").exists():
             print(f"Warning: {SOURCE_DIR / 'pyproject.toml'} not found. 'uv' might fail.")

        subprocess.run(cmd, check=True, cwd=SOURCE_DIR, capture_output=True, text=True)
        print(f"Successfully exported to {REQUIREMENTS_FILE}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error exporting dependencies: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error during export: {e}")
        return False

if __name__ == "__main__":
    run_export()
