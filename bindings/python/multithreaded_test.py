"""Exercise Python callbacks on native benchmark worker threads."""

import gc
import subprocess
import sys
import threading
import weakref
from pathlib import Path


def run_callbacks():
    import google_benchmark as benchmark
    from google_benchmark import _benchmark

    source_package = Path(__file__).resolve().parent / "google_benchmark"
    assert not Path(benchmark.__file__).resolve().is_relative_to(source_package)
    benchmark.initialize([__file__, "--benchmark_filter=python_callback"])

    def run_cycle(
        threads: int, use_property: bool, skip_at: int | None
    ) -> None:
        counts: dict[int, int] = {}
        destroyed: list[bool] = []
        lock = threading.Lock()
        rendezvous = threading.Barrier(threads, timeout=10)

        def python_callback(state):
            assert state.threads == threads
            rendezvous.wait()
            iterations = 0
            if skip_at == 0 and state.thread_index == 0:
                state.skip_with_error("intentional skip before iteration")
            while state.keep_running if use_property else bool(state):
                iterations += 1
                state.counters["callback_iterations"] = iterations
                if skip_at == 1 and state.thread_index == 0:
                    state.skip_with_error("intentional skip during iteration")
                    break
            with lock:
                counts[state.thread_index] = iterations

        finalizer = weakref.finalize(python_callback, destroyed.append, True)
        registered = _benchmark.RegisterBenchmark(
            "python_callback", python_callback
        )
        registered.threads(threads).iterations(16)
        del python_callback, registered
        benchmark.run_benchmarks()
        _benchmark.ClearRegisteredBenchmarks()
        gc.collect()

        assert set(counts) == set(range(threads)), counts
        for index, count in counts.items():
            expected = skip_at if skip_at is not None and index == 0 else 16
            assert count == expected, (index, count, expected)
        assert destroyed == [True]
        assert not finalizer.alive

    for threads in (1, 2, 4, 8):
        for use_property in (False, True):
            for skip_at in (None, 0, 1):
                run_cycle(threads, use_property, skip_at)

    print(
        "PASS: 24 callback cycles, 1/2/4/8 workers, "
        "both iteration APIs, skips, cleanup"
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        run_callbacks()
    else:
        # Native barrier deadlocks must fail the test instead of hanging CI.
        subprocess.run(
            [sys.executable, "-I", __file__, "--child"], check=True, timeout=60
        )
