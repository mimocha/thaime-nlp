"""Interactive CLI tool for reviewing draft benchmark entries.

Displays one entry at a time with formatted Thai word, RTGS romanization,
and all generated variants. The reviewer can approve, edit, discard, or
skip entries. Progress is saved automatically.

This is a rich-based rewrite of the original ANSI-color CLI.

Usage:
    python -m pipelines benchmark word-conversion review
"""

from __future__ import annotations

import json
import os
import readline  # enables arrow keys, history in input()  # noqa: F401
from collections import Counter
from itertools import product
from pathlib import Path

from pipelines.console import console


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _clear_screen() -> None:
    os.system("clear" if os.name != "nt" else "cls")


def display_entry(entry: dict, index: int, total: int) -> None:
    """Display a single benchmark entry for review."""
    status = entry["review_status"]
    status_colors = {
        "pending": "yellow",
        "approved": "green",
        "edited": "blue",
        "discarded": "red",
    }
    color = status_colors.get(status, "white")

    console.print()
    console.print(f"[dim]{'━' * 70}[/dim]")
    console.print(
        f"  Entry [bold cyan]{index + 1}[/bold cyan]/{total}  "
        f"│  [{color} bold]{status.upper()}[/{color} bold]  "
        f"│  Rank #{entry.get('frequency_rank', '?')}"
    )
    console.print(f"[dim]{'━' * 70}[/dim]")

    console.print()
    console.print(f"  Thai word:   [bold magenta]{entry['thai_word']}[/bold magenta]  "
                   f"({entry.get('syllable_count', '?')} syllables)")
    console.print(f"  RTGS:        [bold green]{entry['rtgs_romanization']}[/bold green]")
    console.print(f"  Category:    [cyan]{entry['category']}[/cyan]")

    diff = entry['difficulty']
    diff_colors = {"easy": "green", "medium": "yellow", "hard": "red"}
    console.print(f"  Difficulty:  [{diff_colors.get(diff, 'white')} bold]{diff}[/{diff_colors.get(diff, 'white')} bold]")

    if entry.get("notes"):
        console.print(f"  Notes:       [dim]{entry['notes']}[/dim]")

    # Components
    components = entry.get("components", [])
    if components:
        console.print(f"\n  [bold]Components:[/bold]")
        for i, comp in enumerate(components):
            thai_seg = comp.get('thai_segment', '')
            onset = comp.get('onset', '') or '∅'
            vowel = comp.get('vowel', '') or '∅'
            coda = comp.get('coda', '') or '∅'
            onset_v = comp.get('onset_variants', [])
            vowel_v = comp.get('vowel_variants', [])
            coda_v = comp.get('coda_variants', [])

            seg_label = f"  [{i + 1}] [magenta]{thai_seg}[/magenta]" if thai_seg else f"  [{i + 1}]"
            console.print(f"{seg_label}  "
                           f"[dim]O:[/dim][cyan]{onset}[/cyan] → {onset_v}  "
                           f"[dim]V:[/dim][cyan]{vowel}[/cyan] → {vowel_v}  "
                           f"[dim]C:[/dim][cyan]{coda}[/cyan] → {coda_v}")

    # Variants
    variants = entry.get("variants", [])
    console.print(f"\n  Variants ({len(variants)} total):")
    col_width = 22
    cols = 3
    for row_start in range(0, len(variants), cols):
        row_items = variants[row_start : row_start + cols]
        line = "    "
        for v in row_items:
            if v == entry["rtgs_romanization"]:
                line += f"[green bold]{v:<{col_width}}[/green bold]"
            else:
                line += f"{v:<{col_width}}"
        console.print(line)
    console.print()


def display_help() -> None:
    """Display keyboard shortcuts."""
    console.print(f"[dim]{'━' * 70}[/dim]")
    console.print(f"  [bold]Commands:[/bold]")
    console.print(f"    [green bold]a[/green bold]  approve    — Accept entry as-is")
    console.print(f"    [red bold]d[/red bold]  discard    — Remove entry from benchmark")
    console.print(f"    [yellow bold]s[/yellow bold]  skip       — Leave as pending, move to next")
    console.print(f"    [blue bold]e[/blue bold]  edit       — Edit fields interactively")
    console.print(f"    [cyan bold]v[/cyan bold]  variants   — Add/remove specific variants")
    console.print(f"    [cyan bold]x[/cyan bold]  components — Edit component-level variants")
    console.print(f"    [magenta bold]c[/magenta bold]  category   — Change category")
    console.print(f"    [magenta bold]f[/magenta bold]  difficulty — Change difficulty")
    console.print(f"    [bold]n[/bold]  notes      — Edit notes")
    console.print()
    console.print(f"  [bold]Navigation:[/bold]")
    console.print(f"    [bold]j[/bold]  next | [bold]k[/bold]  prev | [bold]g[/bold]  goto | [bold]p[/bold]  next pending")
    console.print()
    console.print(f"  [bold]Other:[/bold]")
    console.print(f"    [bold]w[/bold]  save | [bold]t[/bold]  stats | [bold]h[/bold]  help | [bold]q[/bold]  quit")
    console.print(f"[dim]{'━' * 70}[/dim]")


def display_stats(entries: list[dict]) -> None:
    """Display review progress statistics."""
    status_counts = Counter(e["review_status"] for e in entries)
    total = len(entries)
    approved = status_counts.get("approved", 0)
    edited = status_counts.get("edited", 0)
    discarded = status_counts.get("discarded", 0)
    pending = status_counts.get("pending", 0)
    reviewed = approved + edited + discarded

    console.print()
    console.print(f"[dim]{'━' * 70}[/dim]")
    console.print(f"  [bold]Review Progress[/bold]")
    console.print(f"[dim]{'━' * 70}[/dim]")
    console.print(f"    Total entries:  {total}")
    console.print(f"    [green]Approved:[/green]       {approved}")
    console.print(f"    [blue]Edited:[/blue]         {edited}")
    console.print(f"    [red]Discarded:[/red]      {discarded}")
    console.print(f"    [yellow]Pending:[/yellow]        {pending}")
    console.print()

    pct = (reviewed / total * 100) if total > 0 else 0
    console.print(f"    Progress: {pct:.1f}% ({reviewed}/{total})")

    accepted = [e for e in entries if e["review_status"] in ("approved", "edited")]
    if accepted:
        cat_dist = Counter(e["category"] for e in accepted)
        diff_dist = Counter(e["difficulty"] for e in accepted)
        console.print(f"\n    [bold]Accepted entries by category:[/bold]")
        for cat, count in sorted(cat_dist.items()):
            console.print(f"      {cat}: {count}")
        console.print(f"\n    [bold]Accepted entries by difficulty:[/bold]")
        for diff, count in sorted(diff_dist.items()):
            console.print(f"      {diff}: {count}")

    console.print(f"[dim]{'━' * 70}[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Edit functions
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = ["common", "ambiguous", "variant", "compound", "similar", "edge"]
_VALID_DIFFICULTIES = ["easy", "medium", "hard"]


def _recompute_variants_from_components(
    entry: dict, max_variants: int = 20,
) -> list[str]:
    """Recompute word-level variants from component-level variant lists."""
    components = entry.get("components", [])
    if not components:
        return entry.get("variants", [])

    syllable_options: list[list[str]] = []
    for comp in components:
        onset_v = comp.get("onset_variants", [""]) or [""]
        vowel_v = comp.get("vowel_variants", [""]) or [""]
        coda_v = comp.get("coda_variants", [""]) or [""]
        syl_variants = sorted({o + v + c for o, v, c in product(onset_v, vowel_v, coda_v)})
        syllable_options.append(syl_variants)

    all_variants: set[str] = set()
    for combo in product(*syllable_options):
        all_variants.add("".join(combo))

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
        console.print(f"\n  Current variants ({len(variants)}):")
        for i, v in enumerate(variants):
            marker = " (RTGS)" if v == rtgs else ""
            console.print(f"    {i + 1:3d}. {v}{marker}")

        console.print(f"\n  Commands: [green]+word[/green] to add, "
                       f"[red]-N[/red] to remove by number, "
                       f"done to finish")
        cmd = input("  > ").strip()

        if cmd.lower() == "done" or cmd == "":
            break
        elif cmd.startswith("+"):
            new_variant = cmd[1:].strip()
            if new_variant and new_variant not in variants:
                variants.append(new_variant)
                variants.sort()
                console.print(f"    [green]Added:[/green] {new_variant}")
            elif new_variant in variants:
                console.print(f"    [yellow]Already exists[/yellow]")
        elif cmd.startswith("-"):
            try:
                idx = int(cmd[1:]) - 1
                if 0 <= idx < len(variants):
                    removed = variants.pop(idx)
                    console.print(f"    [red]Removed:[/red] {removed}")
            except ValueError:
                console.print(f"    [dim]Usage: -N (e.g., -3 to remove #3)[/dim]")

    entry["variants"] = variants
    entry["variant_count"] = len(variants)


def edit_components(entry: dict) -> None:
    """Interactive component-level variant editing."""
    import re as _re

    components = entry.get("components", [])
    if not components:
        console.print(f"  [yellow]No component data available.[/yellow]")
        return

    _COMP_FIELDS = [
        ("onset", "onset_variants", "O"),
        ("vowel", "vowel_variants", "V"),
        ("coda", "coda_variants", "C"),
    ]

    while True:
        console.print(f"\n  [bold cyan]Component Editor[/bold cyan]")
        console.print(f"  [dim]{'─' * 60}[/dim]")
        for i, comp in enumerate(components):
            thai_seg = comp.get('thai_segment', '')
            console.print(f"  Syllable [bold]{i + 1}[/bold] [magenta]{thai_seg}[/magenta]:")
            for key, var_key, label in _COMP_FIELDS:
                g2p_val = comp.get(key, '')
                comp_variants = comp.get(var_key, [])
                if g2p_val or comp_variants:
                    console.print(f"    {label}: [cyan]{g2p_val or '∅'}[/cyan] → {comp_variants}")

        preview = _recompute_variants_from_components(entry)
        console.print(f"\n  → {len(preview)} word variants from these components")

        console.print(f"\n  Commands: [green]S.F +val[/green] add, [red]S.F -val[/red] remove, done to finish")
        cmd = input("  > ").strip()

        if cmd.lower() == "done" or cmd == "":
            break

        m = _re.match(r"^(\d+)\.(O|V|C)\s+([+-])(.+)$", cmd, _re.IGNORECASE)
        if not m:
            console.print(f"  [dim]Format: S.F +val or S.F -val[/dim]")
            continue

        syl_num = int(m.group(1))
        field = m.group(2).upper()
        action = m.group(3)
        value = m.group(4).strip()

        if syl_num < 1 or syl_num > len(components):
            console.print(f"  [red]Syllable must be 1-{len(components)}[/red]")
            continue

        comp = components[syl_num - 1]
        field_map = {"O": "onset_variants", "V": "vowel_variants", "C": "coda_variants"}
        var_key = field_map[field]
        comp_variants = list(comp.get(var_key, []))

        if action == "+":
            if value not in comp_variants:
                comp_variants.append(value)
                comp_variants.sort()
                comp[var_key] = comp_variants
                console.print(f"  [green]Added[/green]")
        elif action == "-":
            if value in comp_variants:
                comp_variants.remove(value)
                comp[var_key] = comp_variants
                console.print(f"  [red]Removed[/red]")

    new_variants = _recompute_variants_from_components(entry)
    old_count = len(entry.get("variants", []))
    entry["variants"] = new_variants
    entry["variant_count"] = len(new_variants)
    console.print(f"  [green]Recomputed:[/green] {old_count} → {len(new_variants)} word variants")


def edit_category(entry: dict) -> None:
    """Change entry category."""
    console.print(f"\n  Current category: [cyan]{entry['category']}[/cyan]")
    console.print(f"  Options: {', '.join(_VALID_CATEGORIES)}")
    new_cat = input("  New category: ").strip().lower()
    if new_cat in _VALID_CATEGORIES:
        entry["category"] = new_cat
        console.print(f"  [green]Updated[/green]")


def edit_difficulty(entry: dict) -> None:
    """Change entry difficulty."""
    console.print(f"\n  Current difficulty: {entry['difficulty']}")
    console.print(f"  Options: {', '.join(_VALID_DIFFICULTIES)}")
    new_diff = input("  New difficulty: ").strip().lower()
    if new_diff in _VALID_DIFFICULTIES:
        entry["difficulty"] = new_diff
        console.print(f"  [green]Updated[/green]")


def edit_notes(entry: dict) -> None:
    """Edit notes field."""
    console.print(f"\n  Current notes: {entry.get('notes', '')}")
    new_notes = input("  New notes (empty to clear): ").strip()
    entry["notes"] = new_notes
    console.print(f"  [green]Updated[/green]")


def edit_entry_full(entry: dict) -> None:
    """Full interactive edit of an entry."""
    console.print(f"\n  [bold]Editing entry:[/bold] {entry['thai_word']}")
    console.print(f"  Press Enter to keep current value.\n")

    print(f"  Category [{entry['category']}]: ", end="")
    new_cat = input().strip().lower()
    if new_cat and new_cat in _VALID_CATEGORIES:
        entry["category"] = new_cat

    print(f"  Difficulty [{entry['difficulty']}]: ", end="")
    new_diff = input().strip().lower()
    if new_diff and new_diff in _VALID_DIFFICULTIES:
        entry["difficulty"] = new_diff

    print(f"  Notes [{entry.get('notes', '')}]: ", end="")
    new_notes = input().strip()
    if new_notes:
        entry["notes"] = new_notes

    print(f"\n  Edit variants? (y/N): ", end="")
    if input().strip().lower() == "y":
        edit_variants(entry)

    console.print(f"  [green]Entry updated[/green]")


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------


def save_data(data: dict, path: Path) -> None:
    """Save review data to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"  [green]Saved[/green] to {path}")


def load_data(path: Path) -> dict:
    """Load review data from JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main review loop
# ---------------------------------------------------------------------------


def _find_next_pending(entries: list[dict], current: int) -> int | None:
    """Find the next pending entry after current index (wrapping)."""
    total = len(entries)
    for offset in range(1, total):
        idx = (current + offset) % total
        if entries[idx]["review_status"] == "pending":
            return idx
    return None


def review_loop(data: dict, save_path: Path) -> None:
    """Main interactive review loop."""
    entries = data["entries"]
    total = len(entries)
    current = 0

    for i, e in enumerate(entries):
        if e["review_status"] == "pending":
            current = i
            break

    _clear_screen()
    console.print(f"\n  [bold cyan]Benchmark Review Tool[/bold cyan]")
    console.print(f"  {total} entries loaded. Press [bold]h[/bold] for help.\n")
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
            console.print(f"\n  [bold]Goodbye![/bold]")
            break
        elif cmd == "a":
            entry["review_status"] = "approved"
            console.print(f"  [green bold]Approved[/green bold]")
            next_pending = _find_next_pending(entries, current)
            current = next_pending if next_pending is not None else min(current + 1, total - 1)
        elif cmd == "d":
            entry["review_status"] = "discarded"
            console.print(f"  [red bold]Discarded[/red bold]")
            next_pending = _find_next_pending(entries, current)
            current = next_pending if next_pending is not None else min(current + 1, total - 1)
        elif cmd == "s":
            current = min(current + 1, total - 1)
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
            current = min(current + 1, total - 1)
        elif cmd == "k":
            current = max(current - 1, 0)
        elif cmd == "g":
            try:
                num = int(input("  Go to entry #: ").strip())
                if 1 <= num <= total:
                    current = num - 1
            except ValueError:
                pass
        elif cmd == "p":
            next_p = _find_next_pending(entries, current)
            if next_p is not None:
                current = next_p
            else:
                console.print(f"  [green bold]No more pending entries![/green bold]")
        elif cmd == "w":
            save_data(data, save_path)
        elif cmd == "t":
            display_stats(entries)
        elif cmd in ("h", "?"):
            display_help()
