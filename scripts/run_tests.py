#!/usr/bin/env python3
"""One-command test runner (Integration Standard #1):
Runs unit, integration, end-to-end, and hard-case tests with zero API keys.
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(str(project_root))
    
    # Ensure src is in PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root) + (os.pathsep + env.get("PYTHONPATH", ""))
    env["APP_ENV"] = "test"
    env["ENABLE_MOCK_SOURCES"] = "true"

    python_exe = sys.executable
    cmd = [python_exe, "-m", "pytest", "tests/", "-v", "--durations=5"]

    print("==========================================================")
    print("IncuBrix B-Roll Engine: Running Full Automated Test Suite")
    print("==========================================================")
    print(f"Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
