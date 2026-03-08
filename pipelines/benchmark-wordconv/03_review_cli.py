"""Step 3: Interactive CLI tool for reviewing draft benchmark entries.

Displays one entry at a time with formatted Thai word, RTGS romanization,
and all generated variants. The reviewer can approve, edit, discard, or
skip entries. Progress is saved automatically.

Output: pipelines/benchmark-wordconv/output/reviewed_benchmark.json

Usage:
    python -m pipelines.benchmark-wordconv.03_review_cli
    python -m pipelines.benchmark-wordconv.03_review_cli --input output/draft_benchmark.json
    python -m pipelines.benchmark-wordconv.03_review_cli --resume
    python -m pipelines.benchmark-wordconv.03_review_cli --stats
"""

from __future__ import annotations

import argparse
import json
import os
import readline  # enables arrow keys, history in input()
import sys
from itertools import product
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

_COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bg_green": "\033[42m",
    "bg_yellow": "\033[43m",
    "bg_red": "\033[41m",
    "bg_blue": "\033[44m",
}


def _c(text: str, *styles: str) -> str:
    """Apply ANSI color/style to text."""
    codes = "".join(_COLORS.get(s, "") for s in styles)
    return f"{codes}{text}{_COLORS['reset']}"


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _clear_screen() -> None:
    os.system("clear" if os.name != "nt" else "cls")


def _status_badge(status: str) -> str:
    """Return a colored badge for review status."""
    badges = {
        "pending": _c(" PENDING ", "bg_yellow", "bold"),
        "approved": _c(" APPROVED ", "bg_green", "bold", "white"),
        "edited": _c(" EDITED ", "bg_blue", "bold", "white"),
        "discarded": _c(" DISCARDED ", "bg_red", "bold", "white"),
    }
    return badges.get(status, status)


def _difficulty_color(difficulty: str) -> str:
    colors = {"easy": "green", "medium": "yellow", "hard": "red"}
    return _c(difficulty, colors.get(difficulty, "white"), "bold")


def display_entry(entry: dict, index: int, total: int) -> None:
    """Display a single benchmark entry for review."""
    print()
    print(_c("━" * 70, "dim"))
    print(
        f"  Entry {_c(str(index + 1), 'bold', 'cyan')}/{total}  "
        f"│  {_status_badge(entry['review_status'])}  "
        f"│  Rank #{entry.get('frequency_rank', '?')}"
    )
    print(_c("━" * 70, "dim"))

    # Thai word (large)
    print()
    print(f"  Thai word:   {_c(entry['thai_word'], 'bold', 'magenta')}  "
          f"({entry.get('syllable_count', '?')} syllables)")
    print(f"  RTGS:        {_c(entry['rtgs_romanization'], 'bold', 'green')}")
    print(f"  Category:    {_c(entry['category'], 'cyan')}")
    print(f"  Difficulty:  {_difficulty_color(entry['difficulty'])}")

    if entry.get("notes"):
        print(f"  Notes:       {_c(entry['notes'], 'dim')}")

    # Component-level decomposition (if available)
    components = entry.get("components", [])
    if components:
        print(f"\n  {_c('Components:', 'bold')}")
        for i, comp in enumerate(components):
            thai_seg = comp.get('thai_segment', '')
            onset = comp.get('onset', '')
            vowel = comp.get('vowel', '')
            coda = comp.get('coda', '')
            onset_v = comp.get('onset_variants', [])
            vowel_v = comp.get('vowel_variants', [])
            coda_v = comp.get('coda_variants', [])

            seg_label = f"  [{i + 1}] {_c(thai_seg, 'magenta')}" if thai_seg else f"  [{i + 1}]"
            print(f"{seg_label}  "
                  f"{_c('O:', 'dim')}{_c(onset or '∅', 'cyan')} → {onset_v}  "
                  f"{_c('V:', 'dim')}{_c(vowel or '∅', 'cyan')} → {vowel_v}  "
                  f"{_c('C:', 'dim')}{_c(coda or '∅', 'cyan')} → {coda_v}")

    # Variants
    variants = entry.get("variants", [])
    print(f"\n  Variants ({len(variants)} total):")

    # Display in columns
    col_width = 22
    cols = 3
    for row_start in range(0, len(variants), cols):
        row_items = variants[row_start : row_start + cols]
        line = "    "
        for j, v in enumerate(row_items):
            # Highlight the RTGS form
            if v == entry["rtgs_romanization"]:
                line += _c(f"{v:<{col_width}}", "green", "bold")
            else:
                line += f"{v:<{col_width}}"
        print(line)

    print()


def display_help() -> None:
    """Display keyboard shortcuts."""
    print(_c("━" * 70, "dim"))
    print(f"  {_c('Commands:', 'bold')}")
    print(f"    {_c('a', 'green', 'bold')}  approve    — Accept entry as-is")
    print(f"    {_c('d', 'red', 'bold')}  discard    — Remove entry from benchmark")
    print(f"    {_c('s', 'yellow', 'bold')}  skip       — Leave as pending, move to next")
    print(f"    {_c('e', 'blue', 'bold')}  edit       — Edit fields interactively")
    print(f"    {_c('v', 'cyan', 'bold')}  variants   — Add/remove specific variants")
    print(f"    {_c('x', 'cyan', 'bold')}  components — Edit component-level variants")
    print(f"    {_c('c', 'magenta', 'bold')}  category   — Change category")
    print(f"    {_c('f', 'magenta', 'bold')}  difficulty — Change difficulty")
    print(f"    {_c('n', 'white', 'bold')}  notes      — Edit notes")
    print()
    print(f"  {_c('Navigation:', 'bold')}")
    print(f"    {_c('j', 'white', 'bold')}  next       — Go to next entry")
    print(f"    {_c('k', 'white', 'bold')}  prev       — Go to previous entry")
    print(f"    {_c('g', 'white', 'bold')}  goto       — Jump to specific entry number")
    print(f"    {_c('p', 'white', 'bold')}  pending    — Jump to next pending entry")
    print()
    print(f"  {_c('Other:', 'bold')}")
    print(f"    {_c('w', 'white', 'bold')}  save       — Save progress")
    print(f"    {_c('t', 'white', 'bold')}  stats      — Show review statistics")
    print(f"    {_c('h', 'white', 'bold')}  help       — Show this help")
    print(f"    {_c('q', 'white', 'bold')}  quit       — Save and quit")
    print(_c("━" * 70, "dim"))


def display_stats(entries: list[dict]) -> None:
    """Display review progress statistics."""
    from collections import Counter

    status_counts = Counter(e["review_status"] for e in entries)
    total = len(entries)
    approved = status_counts.get("approved", 0)
    edited = status_counts.get("edited", 0)
    discarded = status_counts.get("discarded", 0)
    pending = status_counts.get("pending", 0)
    reviewed = approved + edited + discarded

    print()
    print(_c("━" * 70, "dim"))
    print(f"  {_c('Review Progress', 'bold')}")
    print(_c("━" * 70, "dim"))
    print(f"    Total entries:  {total}")
    print(f"    {_c('Approved:', 'green')}       {approved}")
    print(f"    {_c('Edited:', 'blue')}         {edited}")
    print(f"    {_c('Discarded:', 'red')}      {discarded}")
    print(f"    {_c('Pending:', 'yellow')}        {pending}")
    print()
    pct = (reviewed / total * 100) if total > 0 else 0
    bar_len = 40
    filled = int(bar_len * reviewed / total) if total > 0 else 0
    bar = _c("█" * filled, "green") + _c("░" * (bar_len - filled), "dim")
    print(f"    Progress: [{bar}] {pct:.1f}%")

    # Category breakdown of approved+edited
    accepted = [e for e in entries if e["review_status"] in ("approved", "edited")]
    if accepted:
        cat_dist = Counter(e["category"] for e in accepted)
        diff_dist = Counter(e["difficulty"] for e in accepted)
        print(f"\n    {_c('Accepted entries by category:', 'bold')}")
        for cat, count in sorted(cat_dist.items()):
            print(f"      {cat}: {count}")
        print(f"\n    {_c('Accepted entries by difficulty:', 'bold')}")
        for diff, count in sorted(diff_dist.items()):
            print(f"      {diff}: {count}")

    print(_c("━" * 70, "dim"))
    print()


# ---------------------------------------------------------------------------
# Edit functions
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = ["common", "ambiguous", "variant", "compound", "similar", "edge"]
_VALID_DIFFICULTIES = ["easy", "medium", "hard"]


def _recompute_variants_from_components(
    entry: dict, max_variants: int = 20,
) -> list[str]:
    """Recompute word-level variants from component-level variant lists.

    Takes the Cartesian product of onset/vowel/coda variants across all
    syllables and returns the sorted, deduplicated result.
    """
    components = entry.get("components", [])
    if not components:
        return entry.get("variants", [])

    syllable_options: list[list[str]] = []
    for comp in components:
        onset_v = comp.get("onset_variants", [""])
        vowel_v = comp.get("vowel_variants", [""])
        coda_v = comp.get("coda_variants", [""])
        if not onset_v:
            onset_v = [""]
        if not vowel_v:
            vowel_v = [""]
        if not coda_v:
            coda_v = [""]
        syl_variants = sorted({o + v + c for o, v, c in product(onset_v, vowel_v, coda_v)})
        syllable_options.append(syl_variants)

    all_variants: set[str] = set()
    for combo in product(*syllable_options):
        all_variants.add("".join(combo))

    # Always include RTGS
    rtgs = entry.get("rtgs_romanization", "")
    if rtgs:
        all_variants.add(rtgs)

    result = sorted(all_variants)
    if len(result) > max_variants:
        result = [rtgs] + [v for v in result if v != rtgs][: max_variants - 1]
        result.sort()

    return result


def edit_variants(entry: dict) -> None:
    """Interactive variant editing."""
    variants = list(entry.get("variants", []))
    rtgs = entry["rtgs_romanization"]

    while True:
        print(f"\n  Current variants ({len(variants)}):")
        for i, v in enumerate(variants):
            marker = " (RTGS)" if v == rtgs else ""
            print(f"    {i + 1:3d}. {v}{marker}")

        print(f"\n  Commands: {_c('+word', 'green')} to add, "
              f"{_c('-N', 'red')} to remove by number, "
              f"{_c('done', 'white')} to finish")
        cmd = input("  > ").strip()

        if cmd.lower() == "done" or cmd == "":
            break
        elif cmd.startswith("+"):
            new_variant = cmd[1:].strip()
            if new_variant and new_variant not in variants:
                variants.append(new_variant)
                variants.sort()
                print(f"    {_c('Added:', 'green')} {new_variant}")
            elif new_variant in variants:
                print(f"    {_c('Already exists', 'yellow')}")
        elif cmd.startswith("-"):
            try:
                idx = int(cmd[1:]) - 1
                if 0 <= idx < len(variants):
                    removed = variants.pop(idx)
                    print(f"    {_c('Removed:', 'red')} {removed}")
                else:
                    print(f"    {_c('Invalid index', 'red')}")
            except ValueError:
                print(f"    {_c('Usage: -N (e.g., -3 to remove #3)', 'dim')}")

    entry["variants"] = variants
    entry["variant_count"] = len(variants)


def edit_components(entry: dict) -> None:
    """Interactive component-level variant editing.

    Shows each syllable's onset/vowel/coda and their current variant lists.
    Allows adding/removing variants per component, then recomputes the
    full word-level variant list via Cartesian product.
    """
    components = entry.get("components", [])
    if not components:
        print(f"  {_c('No component data available for this entry.', 'yellow')}")
        print(f"  Use {_c('v', 'cyan', 'bold')} to edit word-level variants directly.")
        return

    _COMP_FIELDS = [
        ("onset", "onset_variants", "O"),
        ("vowel", "vowel_variants", "V"),
        ("coda", "coda_variants", "C"),
    ]

    while True:
        # Display current components
        print(f"\n  {_c('Component Editor', 'bold', 'cyan')}")
        print(f"  {_c('─' * 60, 'dim')}")
        for i, comp in enumerate(components):
            thai_seg = comp.get('thai_segment', '')
            print(f"  Syllable {_c(str(i + 1), 'bold')} "
                  f"{_c(thai_seg, 'magenta')}:")
            for key, var_key, label in _COMP_FIELDS:
                g2p_val = comp.get(key, '')
                variants = comp.get(var_key, [])
                if g2p_val or variants:
                    print(f"    {label}: {_c(g2p_val or '∅', 'cyan')} → "
                          f"{_c(str(variants), 'white')}")

        # Compute and show current variant count from components
        preview = _recompute_variants_from_components(entry)
        print(f"\n  → {len(preview)} word variants from these components")

        print(f"\n  Commands: {_c('S.F +val', 'green')} add variant "
              f"(e.g. {_c('1.O +g', 'green')}), "
              f"{_c('S.F -val', 'red')} remove, "
              f"{_c('done', 'white')} to finish")
        print(f"  S=syllable#, F=O/V/C (onset/vowel/coda)")
        cmd = input("  > ").strip()

        if cmd.lower() == "done" or cmd == "":
            break

        # Parse: "1.O +g" or "2.V -aa"
        import re as _re
        m = _re.match(r"^(\d+)\.(O|V|C)\s+([+-])(.+)$", cmd, _re.IGNORECASE)
        if not m:
            print(f"  {_c('Format: S.F +val or S.F -val (e.g. 1.O +g)', 'dim')}")
            continue

        syl_num = int(m.group(1))
        field = m.group(2).upper()
        action = m.group(3)
        value = m.group(4).strip()

        if syl_num < 1 or syl_num > len(components):
            print(f"  {_c(f'Syllable must be 1-{len(components)}', 'red')}")
            continue

        comp = components[syl_num - 1]
        field_map = {"O": "onset_variants", "V": "vowel_variants", "C": "coda_variants"}
        var_key = field_map[field]
        variants = list(comp.get(var_key, []))

        if action == "+":
            if value not in variants:
                variants.append(value)
                variants.sort()
                comp[var_key] = variants
                print(f"  {_c('Added:', 'green')} {value} to syllable {syl_num} {field}")
            else:
                print(f"  {_c('Already exists', 'yellow')}")
        elif action == "-":
            if value in variants:
                variants.remove(value)
                comp[var_key] = variants
                print(f"  {_c('Removed:', 'red')} {value} from syllable {syl_num} {field}")
            else:
                print(f"  {_c('Not found in variant list', 'yellow')}")

    # Recompute word-level variants from the updated components
    new_variants = _recompute_variants_from_components(entry)
    old_count = len(entry.get("variants", []))
    entry["variants"] = new_variants
    entry["variant_count"] = len(new_variants)
    print(f"  {_c('Recomputed:', 'green')} {old_count} → {len(new_variants)} word variants")


def edit_category(entry: dict) -> None:
    """Change entry category."""
    print(f"\n  Current category: {_c(entry['category'], 'cyan')}")
    print(f"  Options: {', '.join(_VALID_CATEGORIES)}")
    new_cat = input("  New category: ").strip().lower()
    if new_cat in _VALID_CATEGORIES:
        entry["category"] = new_cat
        print(f"  {_c('Updated', 'green')}")
    elif new_cat:
        print(f"  {_c('Invalid category', 'red')}")


def edit_difficulty(entry: dict) -> None:
    """Change entry difficulty."""
    print(f"\n  Current difficulty: {_difficulty_color(entry['difficulty'])}")
    print(f"  Options: {', '.join(_VALID_DIFFICULTIES)}")
    new_diff = input("  New difficulty: ").strip().lower()
    if new_diff in _VALID_DIFFICULTIES:
        entry["difficulty"] = new_diff
        print(f"  {_c('Updated', 'green')}")
    elif new_diff:
        print(f"  {_c('Invalid difficulty', 'red')}")


def edit_notes(entry: dict) -> None:
    """Edit notes field."""
    print(f"\n  Current notes: {entry.get('notes', '')}")
    new_notes = input("  New notes (empty to clear): ").strip()
    entry["notes"] = new_notes
    print(f"  {_c('Updated', 'green')}")


def edit_entry_full(entry: dict) -> None:
    """Full interactive edit of an entry."""
    print(f"\n  {_c('Editing entry:', 'bold')} {entry['thai_word']}")
    print(f"  Press Enter to keep current value.\n")

    # Category
    print(f"  Category [{entry['category']}]: ", end="")
    new_cat = input().strip().lower()
    if new_cat and new_cat in _VALID_CATEGORIES:
        entry["category"] = new_cat

    # Difficulty
    print(f"  Difficulty [{entry['difficulty']}]: ", end="")
    new_diff = input().strip().lower()
    if new_diff and new_diff in _VALID_DIFFICULTIES:
        entry["difficulty"] = new_diff

    # Notes
    print(f"  Notes [{entry.get('notes', '')}]: ", end="")
    new_notes = input().strip()
    if new_notes:
        entry["notes"] = new_notes

    # Offer variant editing
    print(f"\n  Edit variants? (y/N): ", end="")
    if input().strip().lower() == "y":
        edit_variants(entry)

    print(f"  {_c('Entry updated', 'green')}")


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------


def save_data(data: dict, path: Path) -> None:
    """Save review data to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  {_c('Saved', 'green')} to {path}")


def load_data(path: Path) -> dict:
    """Load review data from JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main review loop
# ---------------------------------------------------------------------------


def review_loop(data: dict, save_path: Path) -> None:
    """Main interactive review loop."""
    entries = data["entries"]
    total = len(entries)
    current = 0

    # Find first pending entry
    for i, e in enumerate(entries):
        if e["review_status"] == "pending":
            current = i
            break

    _clear_screen()
    print(_c("\n  Benchmark Review Tool v2.0", "bold", "cyan"))
    print(f"  {total} entries loaded. Press {_c('h', 'bold')} for help.\n")
    display_stats(entries)

    while True:
        entry = entries[current]
        display_entry(entry, current, total)
        display_help()

        try:
            cmd = input(f"  [{current + 1}/{total}] > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            save_data(data, save_path)
            break

        if cmd == "q":
            save_data(data, save_path)
            print(f"\n  {_c('Goodbye!', 'bold')}")
            break

        elif cmd == "a":
            entry["review_status"] = "approved"
            print(f"  {_c('✓ Approved', 'green', 'bold')}")
            # Auto-advance to next pending
            next_pending = _find_next_pending(entries, current)
            if next_pending is not None:
                current = next_pending
            elif current < total - 1:
                current += 1

        elif cmd == "d":
            entry["review_status"] = "discarded"
            print(f"  {_c('✗ Discarded', 'red', 'bold')}")
            next_pending = _find_next_pending(entries, current)
            if next_pending is not None:
                current = next_pending
            elif current < total - 1:
                current += 1

        elif cmd == "s":
            # Skip - stay pending, move to next
            if current < total - 1:
                current += 1
            else:
                print(f"  {_c('Already at last entry', 'yellow')}")

        elif cmd == "e":
            edit_entry_full(entry)
            if entry["review_status"] == "pending":
                entry["review_status"] = "edited"

        elif cmd == "v":
            edit_variants(entry)
            if entry["review_status"] == "pending":
                entry["review_status"] = "edited"

        elif cmd == "x":
            edit_components(entry)
            if entry["review_status"] == "pending":
                entry["review_status"] = "edited"

        elif cmd == "c":
            edit_category(entry)

        elif cmd == "f":
            edit_difficulty(entry)

        elif cmd == "n":
            edit_notes(entry)

        elif cmd == "j":
            if current < total - 1:
                current += 1
            else:
                print(f"  {_c('Already at last entry', 'yellow')}")

        elif cmd == "k":
            if current > 0:
                current -= 1
            else:
                print(f"  {_c('Already at first entry', 'yellow')}")

        elif cmd == "g":
            try:
                num = int(input("  Go to entry #: ").strip())
                if 1 <= num <= total:
                    current = num - 1
                else:
                    print(f"  {_c(f'Must be 1-{total}', 'red')}")
            except ValueError:
                print(f"  {_c('Invalid number', 'red')}")

        elif cmd == "p":
            next_p = _find_next_pending(entries, current)
            if next_p is not None:
                current = next_p
            else:
                print(f"  {_c('No more pending entries!', 'green', 'bold')}")

        elif cmd == "w":
            save_data(data, save_path)

        elif cmd == "t":
            display_stats(entries)

        elif cmd == "h" or cmd == "?":
            display_help()

        else:
            print(f"  {_c('Unknown command. Press h for help.', 'dim')}")

        # Auto-save every 10 actions
        # (We track this loosely — just save if status changed)


def _find_next_pending(entries: list[dict], current: int) -> int | None:
    """Find the next pending entry after current index (wrapping)."""
    total = len(entries)
    for offset in range(1, total):
        idx = (current + offset) % total
        if entries[idx]["review_status"] == "pending":
            return idx
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive CLI review tool for benchmark entries."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input JSON path (default: output/draft_benchmark.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output/save JSON path (default: output/reviewed_benchmark.json)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previously saved review file",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics and exit (no interactive mode)",
    )
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else OUTPUT_DIR / "draft_benchmark.json"
    save_path = Path(args.output) if args.output else OUTPUT_DIR / "reviewed_benchmark.json"

    # Load data — always prefer the save file if it exists (auto-resume)
    if save_path.exists():
        print(f"  Resuming from {save_path}")
        data = load_data(save_path)
    elif input_path.exists():
        print(f"  Loading from {input_path}")
        data = load_data(input_path)
    else:
        print(f"  ERROR: No input file found at {input_path}")
        print(f"  Run step 02 first to generate draft_benchmark.json")
        sys.exit(1)

    if args.stats:
        display_stats(data["entries"])
        return

    # Start review loop
    review_loop(data, save_path)


if __name__ == "__main__":
    main()
