"""Quick test: can TLTK run correctly in spawned child processes?

Run from repo root:
    python experiments/test_tltk_multiprocessing.py

Expected output: all 5 words produce identical results in main vs child processes.
If TLTK is not process-safe, you'll see mismatches, hangs, or segfaults.
"""

from concurrent.futures import ProcessPoolExecutor
import tltk

TEST_WORDS = ["สวัสดี", "กรุงเทพ", "ข้าว", "หมู", "ภูเก็ต"]


def process_word(word):
    """Run all 3 TLTK calls in a child process."""
    return {
        "th2roman": tltk.nlp.th2roman(word),
        "g2p": tltk.nlp.g2p(word),
        "syl_segment": tltk.nlp.syl_segment(word),
    }


if __name__ == "__main__":
    # Get reference results from main process
    print("Main process results:")
    main_results = {}
    for w in TEST_WORDS:
        main_results[w] = process_word(w)
        print(f"  {w}: OK")

    # Run same words in child processes (spawn context = safest)
    print("\nChild process results (spawn, 2 workers):")
    with ProcessPoolExecutor(max_workers=2, mp_context=__import__("multiprocessing").get_context("spawn")) as pool:
        child_results = dict(zip(TEST_WORDS, pool.map(process_word, TEST_WORDS)))

    # Compare
    all_match = True
    for w in TEST_WORDS:
        match = main_results[w] == child_results[w]
        status = "MATCH" if match else "MISMATCH"
        print(f"  {w}: {status}")
        if not match:
            all_match = False
            print(f"    main:  {main_results[w]}")
            print(f"    child: {child_results[w]}")

    print(f"\n{'PASS — TLTK is process-safe' if all_match else 'FAIL — results differ across processes'}")
