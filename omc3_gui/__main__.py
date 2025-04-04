from pathlib import Path

this_dir = Path(__file__).parent

# Welcome ---
print("Welcome to omc3_gui!\n")

# Scripts ---
scripts = this_dir.glob("[a-zA-Z]*.py")
print("Available entrypoints:\n")
for script in scripts:
    print(f"omc3_gui.{script.stem}")
print()
