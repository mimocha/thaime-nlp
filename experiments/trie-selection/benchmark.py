"""Benchmark harness for trie data structure comparison.

Benchmarks four trie variants on:
1. Build time
2. Serialized size
3. Memory footprint (via tracemalloc)
4. Common prefix search latency (avg + p99)
5. Exact match latency

Usage:
    python benchmark.py [--dataset PATH] [--runs N]
"""

import argparse
import csv
import gc
import json
import os
import pickle
import random
import string
import sys
import tempfile
import time
import tracemalloc
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Common interface for all trie implementations
# ---------------------------------------------------------------------------

class TrieInterface(ABC):
    """Abstract interface for trie benchmarking."""

    @abstractmethod
    def build(self, keys_with_values: list[tuple[str, Any]]) -> None:
        """Construct the trie from a list of (key, value) pairs."""

    @abstractmethod
    def common_prefix_search(self, input_string: str) -> list[tuple[str, Any]]:
        """Return all keys that are prefixes of input_string, with values."""

    @abstractmethod
    def exact_match(self, key: str) -> Any | None:
        """Return the value for an exact key match, or None."""

    @abstractmethod
    def serialize(self, path: Path) -> None:
        """Serialize the trie to a file."""

    @abstractmethod
    def deserialize(self, path: Path) -> None:
        """Load the trie from a serialized file."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this trie variant."""


# ---------------------------------------------------------------------------
# 1. Standard Trie (dict-of-dicts)
# ---------------------------------------------------------------------------

class StandardTrie(TrieInterface):
    """Naive pointer-based trie using nested Python dicts."""

    def __init__(self):
        self._root: dict = {}
        self._END = "\x00"  # sentinel for end-of-key

    @property
    def name(self) -> str:
        return "Standard Trie (dict-of-dicts)"

    def build(self, keys_with_values: list[tuple[str, Any]]) -> None:
        self._root = {}
        for key, value in keys_with_values:
            node = self._root
            for ch in key:
                node = node.setdefault(ch, {})
            node.setdefault(self._END, []).append(value)

    def common_prefix_search(self, input_string: str) -> list[tuple[str, Any]]:
        results = []
        node = self._root
        prefix = []
        for ch in input_string:
            if ch not in node:
                break
            node = node[ch]
            prefix.append(ch)
            if self._END in node:
                key = "".join(prefix)
                for val in node[self._END]:
                    results.append((key, val))
        return results

    def exact_match(self, key: str) -> Any | None:
        node = self._root
        for ch in key:
            if ch not in node:
                return None
            node = node[ch]
        if self._END in node:
            return node[self._END]
        return None

    def serialize(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self._root, f, protocol=pickle.HIGHEST_PROTOCOL)

    def deserialize(self, path: Path) -> None:
        with open(path, "rb") as f:
            self._root = pickle.load(f)


# ---------------------------------------------------------------------------
# 2. Radix Trie (pygtrie)
# ---------------------------------------------------------------------------

class RadixTrie(TrieInterface):
    """Radix/Patricia trie using pygtrie.CharTrie."""

    def __init__(self):
        import pygtrie
        self._trie = pygtrie.CharTrie()

    @property
    def name(self) -> str:
        return "Radix Trie (pygtrie)"

    def build(self, keys_with_values: list[tuple[str, Any]]) -> None:
        import pygtrie
        self._trie = pygtrie.CharTrie()
        for key, value in keys_with_values:
            if key in self._trie:
                self._trie[key].append(value)
            else:
                self._trie[key] = [value]

    def common_prefix_search(self, input_string: str) -> list[tuple[str, Any]]:
        results = []
        # pygtrie prefixes() returns all prefixes of the given key
        # that exist in the trie
        try:
            for key, values in self._trie.prefixes(input_string):
                for val in values:
                    results.append((key, val))
        except KeyError:
            pass
        return results

    def exact_match(self, key: str) -> Any | None:
        try:
            return self._trie[key]
        except KeyError:
            return None

    def serialize(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self._trie, f, protocol=pickle.HIGHEST_PROTOCOL)

    def deserialize(self, path: Path) -> None:
        with open(path, "rb") as f:
            self._trie = pickle.load(f)


# ---------------------------------------------------------------------------
# 3. Double-Array Trie (datrie / libdatrie)
# ---------------------------------------------------------------------------

class DoubleArrayTrie(TrieInterface):
    """Double-array trie using datrie (libdatrie wrapper).

    datrie stores string values natively. We encode our value list as
    a JSON string to support multiple values per key.
    """

    def __init__(self):
        self._trie = None

    @property
    def name(self) -> str:
        return "Double-Array Trie (datrie)"

    def build(self, keys_with_values: list[tuple[str, Any]]) -> None:
        import datrie

        # Collect all characters used in keys
        all_chars = set()
        # Group values by key
        key_values: dict[str, list] = {}
        for key, value in keys_with_values:
            all_chars.update(key)
            key_values.setdefault(key, []).append(value)

        # datrie requires the alphabet to be specified upfront
        alphabet = "".join(sorted(all_chars))
        self._trie = datrie.Trie(alphabet)

        for key, values in key_values.items():
            # datrie stores a single value per key; encode as JSON
            self._trie[key] = json.dumps(values)

    def common_prefix_search(self, input_string: str) -> list[tuple[str, Any]]:
        results = []
        if self._trie is None:
            return results
        # datrie.Trie.prefixes() returns keys that are prefixes of the input
        for key in self._trie.prefixes(input_string):
            values = json.loads(self._trie[key])
            for val in values:
                results.append((key, val))
        return results

    def exact_match(self, key: str) -> Any | None:
        if self._trie is None:
            return None
        try:
            return json.loads(self._trie[key])
        except KeyError:
            return None

    def serialize(self, path: Path) -> None:
        if self._trie is not None:
            self._trie.save(str(path))

    def deserialize(self, path: Path) -> None:
        import datrie
        self._trie = datrie.Trie.load(str(path))


# ---------------------------------------------------------------------------
# 4. MARISA-Trie
# ---------------------------------------------------------------------------

class MarisaTrie(TrieInterface):
    """MARISA-trie using marisa_trie.BytesTrie.

    Uses BytesTrie to store arbitrary binary values per key.
    Values are encoded as JSON bytes.
    """

    def __init__(self):
        self._trie = None

    @property
    def name(self) -> str:
        return "MARISA-Trie"

    def build(self, keys_with_values: list[tuple[str, Any]]) -> None:
        import marisa_trie

        # Group values by key
        key_values: dict[str, list] = {}
        for key, value in keys_with_values:
            key_values.setdefault(key, []).append(value)

        # Build BytesTrie: list of (key, bytes_value)
        items = []
        for key, values in key_values.items():
            encoded = json.dumps(values).encode("utf-8")
            items.append((key, encoded))

        self._trie = marisa_trie.BytesTrie(items)

    def common_prefix_search(self, input_string: str) -> list[tuple[str, Any]]:
        results = []
        if self._trie is None:
            return results
        # marisa_trie.BytesTrie.prefixes() returns keys that are prefixes
        for key in self._trie.prefixes(input_string):
            for raw_value in self._trie[key]:
                values = json.loads(raw_value.decode("utf-8"))
                for val in values:
                    results.append((key, val))
        return results

    def exact_match(self, key: str) -> Any | None:
        if self._trie is None:
            return None
        try:
            raw_values = self._trie[key]
            if raw_values:
                return json.loads(raw_values[0].decode("utf-8"))
            return None
        except KeyError:
            return None

    def serialize(self, path: Path) -> None:
        if self._trie is not None:
            self._trie.save(str(path))

    def deserialize(self, path: Path) -> None:
        import marisa_trie
        self._trie = marisa_trie.BytesTrie()
        self._trie.load(str(path))


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_dataset(path: Path) -> list[tuple[str, Any]]:
    """Load a synthetic dataset TSV file.

    Returns list of (key, value) tuples where value is (word_id, confidence).
    """
    keys_with_values = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            key = row["romanization_key"]
            value = (int(row["word_id"]), float(row["confidence"]))
            keys_with_values.append((key, value))
    return keys_with_values


def generate_search_inputs(keys: list[str], n: int, rng: random.Random) -> list[str]:
    """Generate random search input strings by extending random keys.

    For common prefix search, we need strings that actual keys are
    prefixes of. We take random existing keys and append extra characters.
    """
    inputs = []
    for _ in range(n):
        base = rng.choice(keys)
        # Append 0–10 random characters to simulate longer input
        extra_len = rng.randint(0, 10)
        extra = "".join(rng.choices(string.ascii_lowercase, k=extra_len))
        inputs.append(base + extra)
    return inputs


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def measure_build_time(trie: TrieInterface, data: list[tuple[str, Any]]) -> float:
    """Measure build time in seconds."""
    gc.collect()
    start = time.perf_counter()
    trie.build(data)
    end = time.perf_counter()
    return end - start


def measure_serialized_size(trie: TrieInterface) -> int:
    """Measure serialized size in bytes."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".trie") as f:
        tmp_path = Path(f.name)
    try:
        trie.serialize(tmp_path)
        return tmp_path.stat().st_size
    finally:
        tmp_path.unlink(missing_ok=True)


def measure_memory_footprint(trie_cls: type, data: list[tuple[str, Any]]) -> int:
    """Measure memory footprint in bytes using tracemalloc."""
    gc.collect()
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()
    trie = trie_cls()
    trie.build(data)
    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Compare snapshots
    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total = sum(s.size_diff for s in stats if s.size_diff > 0)
    return total


def measure_common_prefix_search_latency(
    trie: TrieInterface,
    search_inputs: list[str],
) -> dict[str, float]:
    """Measure common prefix search latency.

    Returns dict with 'avg_ns' and 'p99_ns' keys.
    """
    latencies = []
    for inp in search_inputs:
        start = time.perf_counter_ns()
        trie.common_prefix_search(inp)
        end = time.perf_counter_ns()
        latencies.append(end - start)

    latencies.sort()
    avg_ns = sum(latencies) / len(latencies)
    p99_idx = int(len(latencies) * 0.99)
    p99_ns = latencies[min(p99_idx, len(latencies) - 1)]

    return {"avg_ns": avg_ns, "p99_ns": p99_ns}


def measure_exact_match_latency(
    trie: TrieInterface,
    keys: list[str],
) -> dict[str, float]:
    """Measure exact match latency.

    Returns dict with 'avg_ns' key.
    """
    latencies = []
    for key in keys:
        start = time.perf_counter_ns()
        trie.exact_match(key)
        end = time.perf_counter_ns()
        latencies.append(end - start)

    avg_ns = sum(latencies) / len(latencies)
    return {"avg_ns": avg_ns}


def run_benchmark(
    trie_cls: type,
    data: list[tuple[str, Any]],
    search_inputs: list[str],
    exact_match_keys: list[str],
    num_runs: int = 3,
) -> dict:
    """Run full benchmark for a trie variant.

    Returns dict with all metrics (medians over num_runs).
    """
    build_times = []
    serialized_sizes = []
    memory_footprints = []
    cps_results = []
    em_results = []

    for run_idx in range(num_runs):
        # Build
        trie = trie_cls()
        bt = measure_build_time(trie, data)
        build_times.append(bt)

        # Serialized size (only needs one measurement)
        if run_idx == 0:
            ss = measure_serialized_size(trie)
            serialized_sizes.append(ss)

        # Memory footprint (only needs one measurement — expensive)
        if run_idx == 0:
            mf = measure_memory_footprint(trie_cls, data)
            memory_footprints.append(mf)

        # Common prefix search latency
        cps = measure_common_prefix_search_latency(trie, search_inputs)
        cps_results.append(cps)

        # Exact match latency
        em = measure_exact_match_latency(trie, exact_match_keys)
        em_results.append(em)

    # Take medians
    build_times.sort()
    median_build = build_times[len(build_times) // 2]

    median_cps_avg = sorted(r["avg_ns"] for r in cps_results)[len(cps_results) // 2]
    median_cps_p99 = sorted(r["p99_ns"] for r in cps_results)[len(cps_results) // 2]
    median_em_avg = sorted(r["avg_ns"] for r in em_results)[len(em_results) // 2]

    return {
        "name": trie_cls.__name__,
        "display_name": trie_cls().name,
        "build_time_s": round(median_build, 4),
        "serialized_size_bytes": serialized_sizes[0],
        "memory_footprint_bytes": memory_footprints[0],
        "cps_avg_ns": round(median_cps_avg, 1),
        "cps_p99_ns": round(median_cps_p99, 1),
        "exact_match_avg_ns": round(median_em_avg, 1),
    }


_KB = 1024
_MB = 1024 * 1024


def format_bytes(n: int) -> str:
    """Format byte count as human-readable string."""
    if n < _KB:
        return f"{n} B"
    elif n < _MB:
        return f"{n / _KB:.1f} KB"
    else:
        return f"{n / _MB:.1f} MB"


def format_ns(ns: float) -> str:
    """Format nanoseconds as human-readable string."""
    if ns < 1000:
        return f"{ns:.0f} ns"
    elif ns < 1_000_000:
        return f"{ns / 1000:.1f} µs"
    else:
        return f"{ns / 1_000_000:.1f} ms"


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark trie data structures for common prefix search."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Directory containing synthetic datasets (default: experiments/trie-selection/data/)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Directory for results output (default: experiments/trie-selection/results/)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per benchmark (default: 3)",
    )
    parser.add_argument(
        "--search-queries",
        type=int,
        default=1000,
        help="Number of search queries per benchmark (default: 1000)",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    data_dir = Path(args.data_dir) if args.data_dir else base_dir / "data"
    results_dir = Path(args.results_dir) if args.results_dir else base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    trie_classes = [StandardTrie, RadixTrie, DoubleArrayTrie, MarisaTrie]
    scale_labels = ["10k", "50k", "100k"]

    all_results = {}

    for scale in scale_labels:
        dataset_path = data_dir / f"synthetic_{scale}.tsv"
        if not dataset_path.exists():
            print(f"⚠ Dataset not found: {dataset_path} — skipping {scale}")
            continue

        print(f"\n{'='*60}")
        print(f"  Benchmarking at scale: {scale}")
        print(f"{'='*60}")

        data = load_dataset(dataset_path)
        print(f"  Loaded {len(data)} key-value pairs")

        # Extract keys for search input generation
        keys = list(set(key for key, _ in data))
        rng = random.Random(42)
        search_inputs = generate_search_inputs(keys, args.search_queries, rng)
        exact_match_keys = rng.sample(keys, min(args.search_queries, len(keys)))

        scale_results = []

        for trie_cls in trie_classes:
            print(f"\n  → {trie_cls().name}...")
            try:
                result = run_benchmark(
                    trie_cls, data, search_inputs, exact_match_keys,
                    num_runs=args.runs,
                )
                scale_results.append(result)

                print(f"    Build time:     {result['build_time_s']:.4f} s")
                print(f"    Serialized:     {format_bytes(result['serialized_size_bytes'])}")
                print(f"    Memory:         {format_bytes(result['memory_footprint_bytes'])}")
                print(f"    CPS avg:        {format_ns(result['cps_avg_ns'])}")
                print(f"    CPS p99:        {format_ns(result['cps_p99_ns'])}")
                print(f"    Exact match:    {format_ns(result['exact_match_avg_ns'])}")
            except Exception as e:
                print(f"    ✗ FAILED: {e}")
                scale_results.append({
                    "name": trie_cls.__name__,
                    "display_name": trie_cls().name,
                    "error": str(e),
                })

        all_results[scale] = scale_results

    # Save results
    results_path = results_dir / "benchmark_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Results saved to {results_path}")

    # Print summary table
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    for scale in scale_labels:
        if scale not in all_results:
            continue
        print(f"\n  Scale: {scale}")
        print(f"  {'Variant':<30} {'Build':>8} {'Size':>10} {'Memory':>10} {'CPS avg':>10} {'CPS p99':>10}")
        print(f"  {'-'*78}")
        for r in all_results[scale]:
            if "error" in r:
                print(f"  {r['display_name']:<30} {'ERROR':>8}")
                continue
            print(
                f"  {r['display_name']:<30} "
                f"{r['build_time_s']:>7.3f}s "
                f"{format_bytes(r['serialized_size_bytes']):>10} "
                f"{format_bytes(r['memory_footprint_bytes']):>10} "
                f"{format_ns(r['cps_avg_ns']):>10} "
                f"{format_ns(r['cps_p99_ns']):>10}"
            )


if __name__ == "__main__":
    main()
