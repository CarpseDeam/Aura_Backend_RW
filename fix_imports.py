# fix_imports.py
import os
from pathlib import Path


def fix_blueprint_imports():
    """
    Automatically finds and fixes the import statements in all blueprint files.
    """
    # This script assumes it's in the project root.
    # It will look for the 'src/blueprints' directory.
    project_root = Path(__file__).parent
    blueprints_dir = project_root / "src" / "blueprints"

    if not blueprints_dir.is_dir():
        print(f"❌ Error: Could not find the directory at '{blueprints_dir}'")
        print("Please make sure you have copied the 'blueprints' directory into 'src'.")
        return

    print(f"🔍 Scanning for blueprints in: {blueprints_dir}\n")

    old_import_line = "from foundry.blueprints import Blueprint"
    new_import_line = "from src.foundry.blueprints import Blueprint"
    files_fixed = 0

    # Use rglob to find all .py files, even in subdirectories if you add them later
    for file_path in blueprints_dir.rglob("*.py"):
        try:
            content = file_path.read_text(encoding='utf-8')

            if old_import_line in content:
                new_content = content.replace(old_import_line, new_import_line)
                file_path.write_text(new_content, encoding='utf-8')
                print(f"✅ Fixed import in: {file_path.relative_to(project_root)}")
                files_fixed += 1

        except Exception as e:
            print(f"❌ Error processing file {file_path.name}: {e}")

    print(f"\n✨ Done! Fixed imports in {files_fixed} blueprint files.")


if __name__ == "__main__":
    fix_blueprint_imports()