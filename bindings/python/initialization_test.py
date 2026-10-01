"""Check repeated initialization through installed Python bindings."""

import gc
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import google_benchmark as benchmark


@benchmark.register
@benchmark.option.iterations(1)
def initialization_probe(state):
    while state:
        pass


class InitializationTest(unittest.TestCase):
    def test_repeated_initialization_updates_executable(self):
        self.assertEqual(benchmark.initialize([]), [])
        names = ("first", "second-" * 40, "short", "benchmark-\u03bb")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            for name in names:
                with self.subTest(name=name):
                    argv = [
                        name,
                        "--benchmark_filter=initialization_probe",
                        f"--benchmark_out={output}",
                        "--benchmark_out_format=json",
                        "keep-this-argument",
                    ]
                    self.assertEqual(
                        benchmark.initialize(argv), [name, "keep-this-argument"]
                    )
                    del argv
                    gc.collect()
                    benchmark.run_benchmarks()
                    report = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(report["context"]["executable"], name)
                    self.assertTrue(report["benchmarks"])


if __name__ == "__main__":
    unittest.main()
