"""Run the same application checks locally and in CI using the active Python."""

import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", help="Also audit Python dependencies (requires network access).")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    commands = [
        ["my_site/manage.py", "check"],
        ["my_site/manage.py", "makemigrations", "--check", "--dry-run"],
        ["my_site/manage.py", "test", "blog_app"],
    ]
    if args.audit:
        commands.append([
            "-m", "pip_audit", "--strict",
            "-r", "requirements-dev.txt",
        ])
    for command in commands:
        print(f"Running: python {' '.join(command)}", flush=True)
        result = subprocess.run([sys.executable, *command], cwd=root)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
