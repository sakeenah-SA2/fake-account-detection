"""Build the standalone BotWatch CLI executable with PyInstaller.

Usage:
    pip install pyinstaller
    python build-cli.py

Produces a single self-contained file:
    dist/botwatch.exe   (Windows)
    dist/botwatch       (macOS / Linux)

The executable bundles a Python runtime, so end users need neither Python nor
any packages — it calls the hosted API for predictions.
"""

import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller is not installed. Run:  pip install pyinstaller")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                                   # single executable
        "--console",                                   # keep the terminal window
        "--clean",
        "--name", "botwatch",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build", "pyinstaller"),
        "--specpath", os.path.join(HERE, "build"),
        os.path.join(HERE, "botwatch.py"),
    ]
    subprocess.check_call(cmd)

    exe = "botwatch.exe" if os.name == "nt" else "botwatch"
    print(f"\nDone -> dist/{exe}")


if __name__ == "__main__":
    main()
