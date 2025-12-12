import sys
from pathlib import Path

# Add current directory to path to allow importing local modules
# Build script is likely run from root, so 'build' package is available? 
# Or if run from inside build/, we need to handle that.
# Let's assume run from root as 'python build/build.py'

current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

try:
    import deps
    import merge
except ImportError:
    # Fallback if run from inside the dir
    try:
        import deps
        import merge
    except ImportError:
        print("Error: Could not import build modules. ensure you are running from the project root.")
        sys.exit(1)

def main():
    print("=== Starting Build Process ===")
    
    # Step 1: Export Dependencies
    print("\n--- Step 1: Exporting Dependencies ---")
    if not deps.run_export():
        print("Warning: Dependency export failed or was skipped.")
        # We continue even if export fails, as it might be optional or dev env issue
    
    # Step 2: Merge Files
    print("\n--- Step 2: Merging Files ---")
    try:
        merge.run_merge()
    except Exception as e:
        print(f"Error during merge: {e}")
        sys.exit(1)

    print("\n=== Build Complete ===")

if __name__ == "__main__":
    main()