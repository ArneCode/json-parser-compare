#!/usr/bin/env python3
# AI assistance: written with AI assistance; maintainer reviewed.

"""Plot parse or debug-build benchmark JSON as a bar chart PNG."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import matplotlib.pyplot as plt
import numpy as np


def load_results(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def median_ms(entry: dict) -> float:
    return entry["median_s"] * 1000


def sort_backends_by_time(
    backends: set[str] | list[str],
    times: dict[str, float],
) -> list[str]:
    """Fastest (lowest median) first; missing times last."""
    return sorted(backends, key=lambda b: (times.get(b) is None, times.get(b, float("inf"))))


def plot_parse(data: dict, out_path: pathlib.Path) -> None:
    results = data["results"]
    if not results:
        print("error: no results to plot", file=sys.stderr)
        sys.exit(1)

    all_backends = {r["backend"] for r in results if r.get("median_s") is not None}
    fixtures = data.get("fixtures") or sorted({r["fixture"] for r in results})
    parse_failures = data.get("parse_failures") or [
        {"backend": r["backend"], "fixture": r["fixture"]}
        for r in results
        if r.get("error")
    ]

    by_key = {
        (r["backend"], r["fixture"]): median_ms(r)
        for r in results
        if r.get("median_s") is not None
    }

    # Global bar order: mean median over fixtures each backend actually passed.
    sort_key: dict[str, float] = {}
    for b in all_backends:
        times = [by_key[(b, f)] for f in fixtures if (b, f) in by_key]
        if times:
            sort_key[b] = sum(times) / len(times)
    backends_sorted = sort_backends_by_time(all_backends, sort_key)

    n_fix = len(fixtures)
    fig, axes = plt.subplots(
        1,
        n_fix,
        figsize=(max(12, 8) * max(n_fix, 1) / 2, 5),
        squeeze=False,
        sharey=False,
    )
    axes = axes[0]

    colors = plt.cm.tab10(np.linspace(0, 1, max(len(fixtures), 1)))

    for ax_idx, fixture in enumerate(fixtures):
        ax = axes[ax_idx] if len(fixtures) > 1 else axes[0]
        backends = [b for b in backends_sorted if (b, fixture) in by_key]
        if not backends:
            ax.set_title(f"{fixture} (no successful parses)")
            ax.axis("off")
            continue
        x = np.arange(len(backends))
        values = [by_key[(b, fixture)] for b in backends]
        bars = ax.bar(x, values, color=colors[ax_idx % len(colors)], width=0.7)
        ax.set_title(fixture)
        ax.set_ylabel("median time (ms)")
        ax.set_xticks(x)
        ax.set_xticklabels(backends, rotation=45, ha="right")
        ax.bar_label(bars, fmt="%.1f", padding=2, fontsize=7)

    title = "JSON parse time (hyperfine, release CLI)"
    if data.get("rustc"):
        title += f"\n{data['rustc']}"
    if parse_failures:
        failed = ", ".join(f"{f['backend']}×{f['fixture']}" for f in parse_failures)
        title += f"\nExcluded from chart: {failed}"
    fig.suptitle(title)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {out_path}")


def plot_build(data: dict, out_path: pathlib.Path) -> None:
    results = [r for r in data["results"] if r.get("median_s") is not None]
    if not results:
        print("error: no build results to plot", file=sys.stderr)
        sys.exit(1)

    by_backend = {r["backend"]: r["median_s"] for r in results}
    backends = sort_backends_by_time({r["backend"] for r in results}, by_backend)

    x = np.arange(len(backends))
    values = [by_backend[b] for b in backends]

    fig, ax = plt.subplots(figsize=(max(10, len(backends) * 0.55), 5))
    bars = ax.bar(x, values, color=plt.cm.tab10(0.2), width=0.7)
    ax.set_ylabel("median time (s)")
    ax.set_xticks(x)
    ax.set_xticklabels(backends, rotation=45, ha="right")
    ax.bar_label(bars, fmt="%.1f", padding=2, fontsize=7)

    title = "Debug build time (hyperfine, cargo clean each run)"
    if data.get("rustc"):
        title += f"\n{data['rustc']}"
    if data.get("cpus"):
        title += f"  ·  -j {data['cpus']}"
    fig.suptitle(title)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {out_path}")


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Plot debug build results (single bar per backend) instead of parse results.",
    )
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        default=None,
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=None,
    )
    args = parser.parse_args()

    if args.build:
        in_path = args.input or (repo_root / "results" / "build_results.json")
        out_path = args.output or (repo_root / "results" / "chart_build.png")
    else:
        in_path = args.input or (repo_root / "results" / "results.json")
        out_path = args.output or (repo_root / "results" / "chart.png")

    if not in_path.is_file():
        print(f"error: missing {in_path}", file=sys.stderr)
        sys.exit(1)

    data = load_results(in_path)
    if args.build or data.get("benchmark") == "debug_build":
        plot_build(data, out_path)
    else:
        plot_parse(data, out_path)


if __name__ == "__main__":
    main()
