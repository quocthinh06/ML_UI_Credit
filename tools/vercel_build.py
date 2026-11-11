"""Verify model bundles and omit dependency test data from Vercel functions."""

import importlib.util
import os
from pathlib import Path
import shutil


def remove_library_tests(package):
    for tests in sorted(package.rglob("tests"), reverse=True):
        if tests.is_dir():
            shutil.rmtree(tests)


if __name__ == "__main__":
    from download_model import MODELS, download

    for filename, url, digest in MODELS:
        download(filename, url, digest, verify_only=True)
    # Only strip test fixtures in Vercel's disposable build environment.
    if os.environ.get("VERCEL") == "1":
        for name in ("pandas", "scipy"):
            package = Path(importlib.util.find_spec(name).origin).parent
            remove_library_tests(package)
            print(f"{name}: omitted dependency tests from function bundle.")
