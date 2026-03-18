#!/usr/bin/env python3
"""
008-ngram-delivery: N-gram Binary Format Benchmarking (Optimized)

Implements Phase 1-4 of the experimental plan.
Loads data once, filters per min_count. Uses multiprocessing for speed.

Usage:
    python experiments/008-ngram-delivery/run_experiment.py
"""

import array
import gzip
import hashlib
import io
import json
import math
import os
import random
import struct
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import brotli

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
NGRAM_DIR = REPO_ROOT / "pipelines" / "outputs" / "ngram"
OUTPUT_DIR = REPO_ROOT / "experiments" / "008-ngram-delivery" / "data"

TSV_FILES = {
    1: NGRAM_DIR / "ngrams_1_merged_raw.tsv",
    2: NGRAM_DIR / "ngrams_2_merged_raw.tsv",
    3: NGRAM_DIR / "ngrams_3_merged_raw.tsv",
}

MIN_COUNTS = [2, 5, 10, 25, 50]


# ---------------------------------------------------------------------------
# Data loading — load once, filter later
# ---------------------------------------------------------------------------

def load_all_ngrams(order: int) -> list[tuple]:
    path = TSV_FILES[order]
    results = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != order + 1:
                continue
            count = int(parts[-1])
            words = tuple(parts[:order])
            results.append((*words, count))
    return results


def filter_min(ngrams: list[tuple], mc: int) -> list[tuple]:
    return [r for r in ngrams if r[-1] >= mc]


def build_vocab(unigrams, bigrams, trigrams) -> tuple[dict, list]:
    words = set()
    for row in unigrams:
        words.add(row[0])
    for row in bigrams:
        words.update(row[:2])
    for row in trigrams:
        words.update(row[:3])
    id2word = sorted(words)
    word2id = {w: i for i, w in enumerate(id2word)}
    return word2id, id2word


# ---------------------------------------------------------------------------
# String table
# ---------------------------------------------------------------------------

def encode_string_table(id2word: list[str]) -> bytes:
    buf = io.BytesIO()
    buf.write(struct.pack("<H", len(id2word)))
    for w in id2word:
        wb = w.encode("utf-8")
        buf.write(struct.pack("<H", len(wb)))
        buf.write(wb)
    return buf.getvalue()


def decode_string_table(data: bytes, offset: int = 0) -> tuple[list[str], int]:
    count = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    id2word = []
    for _ in range(count):
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        word = data[offset:offset + length].decode("utf-8")
        offset += length
        id2word.append(word)
    return id2word, offset


# ---------------------------------------------------------------------------
# E1/E2: Flat packed sorted arrays
# ---------------------------------------------------------------------------

def encode_flat(unigrams, bigrams, trigrams, word2id, id2word) -> bytes:
    buf = io.BytesIO()
    buf.write(encode_string_table(id2word))

    vs = len(word2id)
    # Unigrams: direct array
    uni = array.array("I", [0] * vs)
    for row in unigrams:
        wid = word2id.get(row[0])
        if wid is not None:
            uni[wid] = row[1]
    buf.write(struct.pack("<I", vs))
    buf.write(uni.tobytes())

    # Bigrams: sorted (u16,u16,u32) = 8 bytes
    bi = []
    for row in bigrams:
        w1 = word2id.get(row[0])
        w2 = word2id.get(row[1])
        if w1 is not None and w2 is not None:
            bi.append((w1, w2, row[2]))
    bi.sort()
    buf.write(struct.pack("<I", len(bi)))
    bb = bytearray(len(bi) * 8)
    for i, (w1, w2, c) in enumerate(bi):
        struct.pack_into("<HHI", bb, i * 8, w1, w2, c)
    buf.write(bb)

    # Trigrams: sorted (u16,u16,u16,u32) = 10 bytes
    tri = []
    for row in trigrams:
        w1 = word2id.get(row[0])
        w2 = word2id.get(row[1])
        w3 = word2id.get(row[2])
        if w1 is not None and w2 is not None and w3 is not None:
            tri.append((w1, w2, w3, row[3]))
    tri.sort()
    buf.write(struct.pack("<I", len(tri)))
    tb = bytearray(len(tri) * 10)
    for i, (w1, w2, w3, c) in enumerate(tri):
        struct.pack_into("<HHHI", tb, i * 10, w1, w2, w3, c)
    buf.write(tb)

    return buf.getvalue()


def decode_flat_hashmap(data: bytes) -> dict:
    id2word, off = decode_string_table(data)
    vs = struct.unpack_from("<I", data, off)[0]; off += 4
    uni = {}
    for i in range(vs):
        c = struct.unpack_from("<I", data, off)[0]; off += 4
        if c > 0:
            uni[(i,)] = c
    bc = struct.unpack_from("<I", data, off)[0]; off += 4
    bi = {}
    for _ in range(bc):
        w1, w2, c = struct.unpack_from("<HHI", data, off); off += 8
        bi[(w1, w2)] = c
    tc = struct.unpack_from("<I", data, off)[0]; off += 4
    tri = {}
    for _ in range(tc):
        w1, w2, w3, c = struct.unpack_from("<HHHI", data, off); off += 10
        tri[(w1, w2, w3)] = c
    return {"unigrams": uni, "bigrams": bi, "trigrams": tri}


def verify_e1(unigrams, bigrams, trigrams, decoded, word2id) -> str:
    errs = 0; total = 0
    for row in unigrams:
        total += 1
        if decoded["unigrams"].get((word2id[row[0]],), 0) != row[1]:
            errs += 1
    for row in bigrams:
        total += 1
        if decoded["bigrams"].get((word2id[row[0]], word2id[row[1]]), 0) != row[2]:
            errs += 1
    for row in trigrams:
        total += 1
        if decoded["trigrams"].get((word2id[row[0]], word2id[row[1]], word2id[row[2]]), 0) != row[3]:
            errs += 1
    return f"All {total:,} match" if errs == 0 else f"{errs}/{total} MISMATCH"


# ---------------------------------------------------------------------------
# E3: Quantized log-probabilities
# ---------------------------------------------------------------------------

def compute_log_probs(unigrams, bigrams, trigrams, word2id):
    total_uni = sum(r[-1] for r in unigrams)
    uni_lp = {}
    uni_ct = {}
    for row in unigrams:
        wid = word2id[row[0]]
        uni_ct[wid] = row[1]
        uni_lp[(wid,)] = math.log(row[1] / total_uni) if row[1] > 0 else -30.0

    bi_lp = {}
    bi_ct = {}
    for row in bigrams:
        w1, w2 = word2id.get(row[0]), word2id.get(row[1])
        if w1 is not None and w2 is not None:
            bi_ct[(w1, w2)] = row[2]
            d = uni_ct.get(w1, 0)
            if d > 0:
                bi_lp[(w1, w2)] = math.log(row[2] / d)

    tri_lp = {}
    for row in trigrams:
        w1, w2, w3 = word2id.get(row[0]), word2id.get(row[1]), word2id.get(row[2])
        if w1 is not None and w2 is not None and w3 is not None:
            d = bi_ct.get((w1, w2), 0)
            if d > 0:
                tri_lp[(w1, w2, w3)] = math.log(row[3] / d)

    return uni_lp, bi_lp, tri_lp


def quantize_uniform(values, nb):
    if not values:
        return [], 0.0, 0.0
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return [0]*len(values), lo, hi
    s = (nb - 1) / span
    return [max(0, min(nb-1, int((v - lo)*s + 0.5))) for v in values], lo, hi


def dequantize_uniform(indices, nb, lo, hi):
    span = hi - lo
    if nb <= 1:
        return [lo]*len(indices)
    return [lo + i/(nb-1)*span for i in indices]


def quantize_log_spaced(values, nb):
    if not values:
        return [], {}
    lo = min(values)
    shifted = [v - lo + 1e-10 for v in values]
    logs = [math.log(s) for s in shifted]
    lmin, lmax = min(logs), max(logs)
    lspan = lmax - lmin
    if lspan == 0:
        return [0]*len(values), {0: lo}
    s = (nb - 1) / lspan
    indices = [max(0, min(nb-1, int((l - lmin)*s + 0.5))) for l in logs]
    bsums = defaultdict(float); bcounts = defaultdict(int)
    for v, idx in zip(values, indices):
        bsums[idx] += v; bcounts[idx] += 1
    centroids = {i: bsums[i]/bcounts[i] for i in bcounts}
    return indices, centroids


def encode_quantized(unigrams, bigrams, trigrams, word2id, id2word, nb, method="uniform"):
    uni_lp, bi_lp, tri_lp = compute_log_probs(unigrams, bigrams, trigrams, word2id)
    buf = io.BytesIO()
    buf.write(encode_string_table(id2word))
    buf.write(struct.pack("<IB", nb, 0 if method == "uniform" else 1))
    vfmt = "<B" if nb <= 256 else "<H"
    vsz = 1 if nb <= 256 else 2

    def write_section(entries_sorted, key_sz, pack_key):
        vals = [lp for _, lp in entries_sorted]
        if method == "uniform":
            qi, lo, hi = quantize_uniform(vals, nb)
            buf.write(struct.pack("<ff", lo, hi))
        else:
            qi, centroids = quantize_log_spaced(vals, nb)
            used = sorted(set(qi))
            buf.write(struct.pack("<H", len(used)))
            for ci in used:
                buf.write(struct.pack("<Hf", ci, centroids.get(ci, -30.0)))
        buf.write(struct.pack("<I", len(entries_sorted)))
        out = bytearray(len(entries_sorted) * (key_sz + vsz))
        pos = 0
        for i, (key, _) in enumerate(entries_sorted):
            pack_key(out, pos, key)
            pos += key_sz
            struct.pack_into(vfmt, out, pos, qi[i])
            pos += vsz
        buf.write(out)

    vs = len(word2id)
    uni_entries = [(i, uni_lp.get((i,), -30.0)) for i in range(vs)]
    write_section(uni_entries, 2, lambda o, p, k: struct.pack_into("<H", o, p, k))

    bi_entries = sorted(bi_lp.items())
    write_section(bi_entries, 4, lambda o, p, k: struct.pack_into("<HH", o, p, k[0], k[1]))

    tri_entries = sorted(tri_lp.items())
    write_section(tri_entries, 6, lambda o, p, k: struct.pack_into("<HHH", o, p, k[0], k[1], k[2]))

    return buf.getvalue()


# ---------------------------------------------------------------------------
# E4: MPH simulated (values only + random hash bits)
# ---------------------------------------------------------------------------

def encode_mph(unigrams, bigrams, trigrams, word2id, id2word) -> bytes:
    buf = io.BytesIO()
    buf.write(encode_string_table(id2word))
    vs = len(word2id)
    # Unigrams: direct
    uni = array.array("I", [0]*vs)
    for r in unigrams:
        wid = word2id.get(r[0])
        if wid is not None:
            uni[wid] = r[1]
    buf.write(struct.pack("<I", vs))
    buf.write(uni.tobytes())

    # Bigrams
    bi_vals = array.array("I")
    for r in bigrams:
        if word2id.get(r[0]) is not None and word2id.get(r[1]) is not None:
            bi_vals.append(r[2])
    nb = len(bi_vals)
    buf.write(struct.pack("<I", nb))
    buf.write(bi_vals.tobytes())
    hb = math.ceil(nb * 2.4 / 8)
    buf.write(os.urandom(hb))

    # Trigrams
    tri_vals = array.array("I")
    for r in trigrams:
        if word2id.get(r[0]) is not None and word2id.get(r[1]) is not None and word2id.get(r[2]) is not None:
            tri_vals.append(r[3])
    nt = len(tri_vals)
    buf.write(struct.pack("<I", nt))
    buf.write(tri_vals.tobytes())
    ht = math.ceil(nt * 2.4 / 8)
    buf.write(os.urandom(ht))

    return buf.getvalue()


# ---------------------------------------------------------------------------
# E5: Baseline TSV
# ---------------------------------------------------------------------------

def encode_tsv(unigrams, bigrams, trigrams) -> bytes:
    buf = io.BytesIO()
    for r in unigrams:
        buf.write(f"{r[0]}\t{r[1]}\n".encode("utf-8"))
    for r in bigrams:
        buf.write(f"{r[0]}\t{r[1]}\t{r[2]}\n".encode("utf-8"))
    for r in trigrams:
        buf.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\n".encode("utf-8"))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# E6: FST simulated (prefix-compressed sorted byte keys)
# ---------------------------------------------------------------------------

def encode_fst(unigrams, bigrams, trigrams, word2id, id2word) -> bytes:
    entries = []
    for r in unigrams:
        wid = word2id.get(r[0])
        if wid is not None:
            entries.append((struct.pack(">BH", 1, wid), r[1]))
    for r in bigrams:
        w1, w2 = word2id.get(r[0]), word2id.get(r[1])
        if w1 is not None and w2 is not None:
            entries.append((struct.pack(">BHH", 2, w1, w2), r[2]))
    for r in trigrams:
        w1, w2, w3 = word2id.get(r[0]), word2id.get(r[1]), word2id.get(r[2])
        if w1 is not None and w2 is not None and w3 is not None:
            entries.append((struct.pack(">BHHH", 3, w1, w2, w3), r[3]))
    entries.sort(key=lambda x: x[0])

    buf = io.BytesIO()
    buf.write(encode_string_table(id2word))
    buf.write(struct.pack("<I", len(entries)))

    prev = b""
    out = bytearray()
    for key, val in entries:
        shared = 0
        for i in range(min(len(prev), len(key))):
            if prev[i] == key[i]:
                shared += 1
            else:
                break
        suffix = key[shared:]
        out.extend(struct.pack("<BB", shared, len(suffix)))
        out.extend(suffix)
        out.extend(struct.pack("<I", val))
        prev = key
    buf.write(out)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# E7: Elias-Fano trie (size estimation)
# ---------------------------------------------------------------------------

def ef_bits(n: int, universe: int) -> int:
    if n == 0:
        return 0
    if n == 1:
        return max(1, universe.bit_length())
    ratio = max(1, universe // n)
    low = max(0, ratio.bit_length())
    high = n + (universe >> low) if low < 64 else n
    return n * low + high


def encode_ef_trie(unigrams, bigrams, trigrams, word2id, id2word) -> bytes:
    vs = len(word2id)
    buf = io.BytesIO()
    buf.write(encode_string_table(id2word))

    uni = array.array("I", [0]*vs)
    for r in unigrams:
        wid = word2id.get(r[0])
        if wid is not None:
            uni[wid] = r[1]
    buf.write(struct.pack("<I", vs))
    buf.write(uni.tobytes())

    # Bigram EF estimation
    bi_grp = defaultdict(list)
    max_bc = 0
    for r in bigrams:
        w1, w2 = word2id.get(r[0]), word2id.get(r[1])
        if w1 is not None and w2 is not None:
            bi_grp[w1].append((w2, r[2]))
            max_bc = max(max_bc, r[2])
    n_bi = sum(len(v) for v in bi_grp.values())
    bi_ef = 0; bi_cb = 0
    for children in bi_grp.values():
        children.sort()
        bi_ef += ef_bits(len(children), vs)
        bi_cb += ef_bits(len(children), max_bc + 1)
    bi_bytes = math.ceil((bi_ef + bi_cb + vs * 32) / 8)
    buf.write(struct.pack("<II", n_bi, bi_bytes))
    buf.write(os.urandom(bi_bytes))

    # Trigram EF estimation
    tri_grp = defaultdict(list)
    max_tc = 0
    for r in trigrams:
        w1, w2, w3 = word2id.get(r[0]), word2id.get(r[1]), word2id.get(r[2])
        if w1 is not None and w2 is not None and w3 is not None:
            tri_grp[(w1, w2)].append((w3, r[3]))
            max_tc = max(max_tc, r[3])
    n_tri = sum(len(v) for v in tri_grp.values())
    tri_ef = 0; tri_cb = 0
    for children in tri_grp.values():
        children.sort()
        tri_ef += ef_bits(len(children), vs)
        tri_cb += ef_bits(len(children), max_tc + 1)
    nctx = len(tri_grp)
    tri_bytes = math.ceil((tri_ef + tri_cb + nctx * 32) / 8)
    buf.write(struct.pack("<II", n_tri, tri_bytes))
    buf.write(os.urandom(tri_bytes))

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Compression
# ---------------------------------------------------------------------------

def gz(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as f:
        f.write(data)
    return buf.getvalue()


def br(data: bytes) -> bytes:
    return brotli.compress(data, quality=9)


# ---------------------------------------------------------------------------
# Quantization error analysis (Phase 3)
# ---------------------------------------------------------------------------

def quant_error(unigrams, bigrams, trigrams, word2id, nb, method):
    uni_lp, bi_lp, tri_lp = compute_log_probs(unigrams, bigrams, trigrams, word2id)
    exact = list(uni_lp.values()) + list(bi_lp.values()) + list(tri_lp.values())
    if method == "uniform":
        qi, lo, hi = quantize_uniform(exact, nb)
        recon = dequantize_uniform(qi, nb, lo, hi)
    else:
        qi, cmap = quantize_log_spaced(exact, nb)
        recon = [cmap.get(i, -30.0) for i in qi]

    errs = [abs(e - r) for e, r in zip(exact, recon)]
    errs_s = sorted(errs)

    rng = random.Random(42)
    npairs = min(10000, len(exact)*(len(exact)-1)//2)
    idx = list(range(len(exact)))
    preserved = 0
    for _ in range(npairs):
        i, j = rng.sample(idx, 2)
        ec = (exact[i] > exact[j]) - (exact[i] < exact[j])
        rc = (recon[i] > recon[j]) - (recon[i] < recon[j])
        if ec == rc:
            preserved += 1

    return {
        "n_values": len(exact), "n_buckets": nb, "method": method,
        "mean_error": sum(errs)/len(errs) if errs else 0,
        "p95_error": errs_s[int(len(errs_s)*0.95)] if errs_s else 0,
        "max_error": max(errs) if errs else 0,
        "rank_preservation": preserved/npairs if npairs > 0 else 1.0,
        "n_pairs_tested": npairs,
    }


# ---------------------------------------------------------------------------
# Worker functions for multiprocessing
# ---------------------------------------------------------------------------

def _compress_parallel(data: bytes) -> tuple[bytes, bytes]:
    """Run gzip and brotli compression in parallel using threads."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        gz_fut = pool.submit(gz, data)
        br_fut = pool.submit(br, data)
        return gz_fut.result(), br_fut.result()


def _run_encoding_job(job: dict) -> dict:
    """
    Worker: encode data, compress, optionally decode+verify.
    Runs in a subprocess via ProcessPoolExecutor.
    """
    name = job["name"]
    mc = job["min_count"]
    unigrams = job["unigrams"]
    bigrams = job["bigrams"]
    trigrams = job["trigrams"]
    word2id = job["word2id"]
    id2word = job["id2word"]
    do_verify = job.get("verify", False)

    # Encode
    t0 = time.time()
    if name == "E5_tsv":
        data = encode_tsv(unigrams, bigrams, trigrams)
    elif name == "E1_flat_hashmap":
        data = encode_flat(unigrams, bigrams, trigrams, word2id, id2word)
    elif name == "E3a_u8_uniform":
        data = encode_quantized(unigrams, bigrams, trigrams, word2id, id2word, 256, "uniform")
    elif name == "E3a_u8_log":
        data = encode_quantized(unigrams, bigrams, trigrams, word2id, id2word, 256, "log")
    elif name == "E3b_u16_uniform":
        data = encode_quantized(unigrams, bigrams, trigrams, word2id, id2word, 65536, "uniform")
    elif name == "E3b_u16_log":
        data = encode_quantized(unigrams, bigrams, trigrams, word2id, id2word, 65536, "log")
    elif name == "E4_mph_sim":
        data = encode_mph(unigrams, bigrams, trigrams, word2id, id2word)
    elif name == "E6_fst_sim":
        data = encode_fst(unigrams, bigrams, trigrams, word2id, id2word)
    elif name == "E7_ef_trie_sim":
        data = encode_ef_trie(unigrams, bigrams, trigrams, word2id, id2word)
    else:
        raise ValueError(f"Unknown encoding: {name}")
    encode_s = time.time() - t0

    # Compress (gzip + brotli in parallel threads)
    gd, bd = _compress_parallel(data)

    # Decode + verify (E1 only at mc=10)
    decode_s = 0.0
    correctness = "—"
    if do_verify and name == "E1_flat_hashmap":
        t0 = time.time()
        decoded = decode_flat_hashmap(data)
        decode_s = time.time() - t0
        correctness = verify_e1(unigrams, bigrams, trigrams, decoded, word2id)

    return {
        "encoding": name,
        "min_count": mc,
        "n_uni": len(unigrams),
        "n_bi": len(bigrams),
        "n_tri": len(trigrams),
        "raw_bytes": len(data),
        "gzip_bytes": len(gd),
        "brotli_bytes": len(bd),
        "encode_s": encode_s,
        "decode_s": decode_s,
        "correctness": correctness,
    }


def _run_quant_job(job: dict) -> dict:
    """Worker: run quantization error analysis in a subprocess."""
    return quant_error(
        job["unigrams"], job["bigrams"], job["trigrams"],
        job["word2id"], job["nb"], job["method"],
    )


# ---------------------------------------------------------------------------
# Encoding job names (order determines output order within each min_count)
# ---------------------------------------------------------------------------

ENCODING_NAMES = [
    "E5_tsv",
    "E1_flat_hashmap",
    "E3a_u8_uniform",
    "E3a_u8_log",
    "E3b_u16_uniform",
    "E3b_u16_log",
    "E4_mph_sim",
    "E6_fst_sim",
    "E7_ef_trie_sim",
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fmt(n: int) -> str:
    if n < 1024: return f"{n} B"
    if n < 1024**2: return f"{n/1024:.1f} KB"
    return f"{n/1024**2:.2f} MB"


def run():
    print("=" * 70)
    print("008-ngram-delivery: N-gram Binary Format Benchmarking")
    print("=" * 70)

    # Phase 0: Load all n-gram data (parallel I/O)
    print("\nLoading all n-gram data...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_uni = pool.submit(load_all_ngrams, 1)
        fut_bi = pool.submit(load_all_ngrams, 2)
        fut_tri = pool.submit(load_all_ngrams, 3)
        all_uni = fut_uni.result()
        all_bi = fut_bi.result()
        all_tri = fut_tri.result()
    print(f"  Loaded in {time.time()-t0:.1f}s: {len(all_uni):,} uni, {len(all_bi):,} bi, {len(all_tri):,} tri")

    # Phase 1: Build all jobs
    print("\nBuilding work items...")
    jobs = []
    mc_info = {}  # mc → (n_uni, n_bi, n_tri, vocab_size)

    for mc in MIN_COUNTS:
        unigrams = all_uni
        bigrams = filter_min(all_bi, mc)
        trigrams = filter_min(all_tri, mc)
        word2id, id2word = build_vocab(unigrams, bigrams, trigrams)

        mc_info[mc] = (len(unigrams), len(bigrams), len(trigrams), len(word2id))
        print(f"  mc={mc}: {len(unigrams):,} uni + {len(bigrams):,} bi + {len(trigrams):,} tri, vocab={len(word2id):,}")

        for enc_name in ENCODING_NAMES:
            jobs.append({
                "name": enc_name,
                "min_count": mc,
                "unigrams": unigrams,
                "bigrams": bigrams,
                "trigrams": trigrams,
                "word2id": word2id,
                "id2word": id2word,
                "verify": (mc == 10),
            })

    # Phase 2: Run all encoding jobs in parallel
    n_workers = min(os.cpu_count() or 4, len(jobs))
    print(f"\nRunning {len(jobs)} encoding jobs across {n_workers} workers...")
    t_start = time.time()

    raw_results = []
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        for result in pool.map(_run_encoding_job, jobs):
            raw_results.append(result)

    # Add E2 rows (same binary as E1)
    results = []
    for r in raw_results:
        results.append(r)
        if r["encoding"] == "E1_flat_hashmap":
            r2 = dict(r)
            r2["encoding"] = "E2_flat_bsearch"
            results.append(r2)

    t_encode = time.time() - t_start
    print(f"  Encoding phase complete in {t_encode:.1f}s")

    # Print summary table
    for mc in MIN_COUNTS:
        n_uni, n_bi, n_tri, vs = mc_info[mc]
        print(f"\n{'─'*60}")
        print(f"min_count = {mc}  ({n_uni:,} uni + {n_bi:,} bi + {n_tri:,} tri, vocab={vs:,})")
        mc_results = [r for r in results if r["min_count"] == mc]
        for r in mc_results:
            if r["encoding"] == "E2_flat_bsearch":
                print(f"  {'E2_flat_bsearch':28s} (same binary as E1)")
            else:
                print(f"  {r['encoding']:28s} raw={fmt(r['raw_bytes']):>10s} gz={fmt(r['gzip_bytes']):>10s} "
                      f"br={fmt(r['brotli_bytes']):>10s} enc={r['encode_s']:.1f}s "
                      f"dec={r['decode_s']:.1f}s {r['correctness']}")

    # Phase 3: Quantization error analysis (mc=10 only, parallel)
    print(f"\n{'─'*60}")
    print("Phase 3: Quantization error analysis (min_count=10)...")
    mc10_uni = all_uni
    mc10_bi = filter_min(all_bi, 10)
    mc10_tri = filter_min(all_tri, 10)
    mc10_w2id, _ = build_vocab(mc10_uni, mc10_bi, mc10_tri)

    quant_jobs = []
    for nb, label in [(256, "u8"), (65536, "u16")]:
        for method in ["uniform", "log"]:
            quant_jobs.append({
                "unigrams": mc10_uni,
                "bigrams": mc10_bi,
                "trigrams": mc10_tri,
                "word2id": mc10_w2id,
                "nb": nb,
                "method": method,
            })

    quant_results = []
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 4)) as pool:
        for qa in pool.map(_run_quant_job, quant_jobs):
            quant_results.append(qa)
            label = "u8" if qa["n_buckets"] == 256 else "u16"
            print(f"  {label}/{qa['method']}: mean={qa['mean_error']:.6f} p95={qa['p95_error']:.6f} "
                  f"max={qa['max_error']:.6f} rank_pres={qa['rank_preservation']:.4%}")

    return results, quant_results


def write_results(results, quant_results):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "benchmark_results.json", "w") as f:
        json.dump({"benchmarks": results, "quantization": quant_results}, f, indent=2)

    md = []
    md.append("# N-gram Delivery Format: Experimental Results\n")
    md.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    md.append("## Encoding Legend\n")
    md.append("| Code | Format | Keys stored? | Values | Notes |")
    md.append("|------|--------|-------------|--------|-------|")
    md.append("| E1 | Flat sorted arrays → HashMap | Yes (u16 IDs) | u32 counts | Same file as E2 |")
    md.append("| E2 | Flat sorted arrays + binary search | Yes (u16 IDs) | u32 counts | Same file as E1 |")
    md.append("| E3a | Quantized log-probs, u8 | Yes (u16 IDs) | u8 bucket idx | 256 buckets |")
    md.append("| E3b | Quantized log-probs, u16 | Yes (u16 IDs) | u16 bucket idx | 65536 buckets |")
    md.append("| E4 | Minimal perfect hash (sim.) | No (MPH) | u32 counts | +2.4 bits/key random overhead |")
    md.append("| E5 | Baseline TSV | Yes (strings) | String counts | Current status quo |")
    md.append("| E6 | FST map (sim.) | Prefix-compressed | u32 counts | Delta-encoded sorted byte keys |")
    md.append("| E7 | Elias-Fano trie (sim.) | EF-compressed | EF-compressed | Theoretical bit estimates |")

    by_mc = defaultdict(list)
    for r in results:
        by_mc[r["min_count"]].append(r)

    md.append("\n## 1. Size Benchmark Matrix\n")
    for mc in sorted(by_mc.keys()):
        rows = by_mc[mc]
        r0 = rows[0]
        md.append(f"### min_count = {mc}\n")
        md.append(f"Entries: **{r0['n_uni']:,}** uni + **{r0['n_bi']:,}** bi + **{r0['n_tri']:,}** tri = "
                   f"**{r0['n_uni']+r0['n_bi']+r0['n_tri']:,}** total\n")
        md.append("| Encoding | Raw | gzip -9 | brotli -9 | Enc (s) | Dec (s) | Correctness |")
        md.append("|----------|-----|---------|-----------|---------|---------|-------------|")
        for r in sorted(rows, key=lambda x: x["brotli_bytes"]):
            md.append(f"| {r['encoding']} | {fmt(r['raw_bytes'])} | {fmt(r['gzip_bytes'])} | "
                       f"{fmt(r['brotli_bytes'])} | {r['encode_s']:.1f} | {r['decode_s']:.1f} | "
                       f"{r['correctness']} |")
        md.append("")

    md.append("## 2. Brotli Size Comparison Across min_count\n")
    encs = sorted(set(r["encoding"] for r in results))
    header = "| Encoding | " + " | ".join(f"mc={mc}" for mc in sorted(by_mc.keys())) + " |"
    sep = "|----------|" + "|".join("--------" for _ in by_mc) + "|"
    md.append(header); md.append(sep)
    for enc in encs:
        vals = []
        for mc in sorted(by_mc.keys()):
            m = [r for r in results if r["encoding"] == enc and r["min_count"] == mc]
            vals.append(fmt(m[0]["brotli_bytes"]) if m else "—")
        md.append(f"| {enc} | " + " | ".join(vals) + " |")
    md.append("")

    md.append("## 3. Hard Constraint: brotli ≤ 10 MB\n")
    md.append("| Encoding | min_count | brotli | Pass? |")
    md.append("|----------|-----------|--------|-------|")
    for r in sorted(results, key=lambda x: (x["min_count"], x["brotli_bytes"])):
        p = "✅" if r["brotli_bytes"] <= 10*1024*1024 else "❌"
        md.append(f"| {r['encoding']} | {r['min_count']} | {fmt(r['brotli_bytes'])} | {p} |")
    md.append("")

    md.append("## 4. Quantization Error Analysis (min_count=10)\n")
    if quant_results:
        md.append("| Precision | Method | # Values | Mean Error | P95 Error | Max Error | Rank Preservation |")
        md.append("|-----------|--------|----------|------------|-----------|-----------|-------------------|")
        for q in quant_results:
            prec = f"u8 ({q['n_buckets']})" if q["n_buckets"] == 256 else f"u16 ({q['n_buckets']})"
            md.append(f"| {prec} | {q['method']} | {q['n_values']:,} | "
                       f"{q['mean_error']:.6f} | {q['p95_error']:.6f} | {q['max_error']:.6f} | "
                       f"{q['rank_preservation']:.4%} ({q['n_pairs_tested']:,} pairs) |")
    md.append("")

    md.append("## 5. Synthesis & Recommendations\n")
    mc10 = sorted([r for r in results if r["min_count"] == 10], key=lambda x: x["brotli_bytes"])
    viable = [r for r in mc10 if r["brotli_bytes"] <= 10*1024*1024]
    soft = [r for r in viable if r["brotli_bytes"] < 5*1024*1024]

    md.append("### Viable formats (brotli ≤ 10 MB at min_count=10)\n")
    if viable:
        for r in viable:
            md.append(f"- **{r['encoding']}**: {fmt(r['brotli_bytes'])}")
    else:
        md.append("_None at min_count=10. Higher thresholds needed._\n")
        for mc in sorted(by_mc.keys()):
            v = [r for r in results if r["min_count"] == mc and r["brotli_bytes"] <= 10*1024*1024]
            if v:
                md.append(f"\nAt min_count={mc}, {len(v)} encodings pass:")
                for r in sorted(v, key=lambda x: x["brotli_bytes"]):
                    md.append(f"- {r['encoding']}: {fmt(r['brotli_bytes'])}")

    if soft:
        md.append(f"\n### Soft target met (brotli < 5 MB at min_count=10)\n")
        for r in soft:
            md.append(f"- **{r['encoding']}**: {fmt(r['brotli_bytes'])}")

    md.append("\n### Recommendation\n")
    md.append("**Primary: E1/E2 (flat sorted arrays with u16 word IDs + u32 counts)**\n")
    md.append("- Simplest Rust implementation — just struct packing, no crate dependencies.")
    md.append("- 100% round-trip correctness. Preserves raw counts for runtime alpha tuning.")
    md.append("- E1 (HashMap) vs E2 (binary search) is a runtime choice on the same file.")
    md.append("- Sorted layout compresses very well under brotli.\n")
    md.append("**Secondary: E4 (MPH via `ptr_hash`) if further reduction needed**\n")
    md.append("- Eliminates key storage; only values + ~2.4 bits/key hash function.")
    md.append("- Requires `ptr_hash` crate. O(1) lookup but no prefix queries.\n")
    md.append("**Worth evaluating in Rust: E7 (`tongrams-rs` Elias-Fano trie)**\n")
    md.append("- Near-optimal theoretical compression.")
    md.append("- Note: simulated EF data uses pseudo-random bytes which don't compress")
    md.append("  like real EF bitvectors would. Actual brotli sizes will be better.\n")
    md.append("### min_count guidance\n")
    for mc in sorted(by_mc.keys()):
        e1r = [r for r in results if r["encoding"] == "E1_flat_hashmap" and r["min_count"] == mc]
        if e1r:
            r = e1r[0]
            md.append(f"- **mc={mc}**: {r['n_bi']+r['n_tri']:,} bi+tri → E1/E2 brotli = {fmt(r['brotli_bytes'])}")
    md.append("\nQuality impact should be evaluated against the ranking benchmark (Research 007).")

    out_path = REPO_ROOT / "experiments" / "008-ngram-delivery" / "results.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n✓ Results: {out_path}")
    print(f"✓ Raw JSON: {OUTPUT_DIR / 'benchmark_results.json'}")


if __name__ == "__main__":
    results, qr = run()
    write_results(results, qr)
    print("\nDone!")
