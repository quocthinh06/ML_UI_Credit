import importlib.util
from pathlib import Path
import tempfile
import unittest


class VercelBuildTests(unittest.TestCase):
    def test_pruning_keeps_runtime_files_and_is_repeatable(self):
        spec = importlib.util.spec_from_file_location(
            "vercel_build", Path(__file__).resolve().parents[1] / "tools/vercel_build.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            runtime = package / "runtime.py"
            runtime.write_text("VALUE = 1")
            tests = package / "submodule/tests"
            tests.mkdir(parents=True)
            (tests / "fixture.bin").write_bytes(b"test data")
            module.remove_library_tests(package)
            module.remove_library_tests(package)
            self.assertFalse(tests.exists())
            self.assertEqual(runtime.read_text(), "VALUE = 1")


if __name__ == "__main__":
    unittest.main()
