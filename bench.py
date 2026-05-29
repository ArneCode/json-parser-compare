#!/usr/bin/env python3
# AI assistance: written with AI assistance; maintainer reviewed.

"""Benchmark JSON parser examples: parse (default) and optional debug build times."""

from __future__ import annotations

import argparse
import datetime
import json
import multiprocessing
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import tempfile


CHART_SKIP = frozenset({"null"})


def hyperfine_warmup() -> str:
    return os.environ.get("BENCH_WARMUP", "3")


def hyperfine_min_runs() -> str:
    return os.environ.get("BENCH_MIN_RUNS", "10")


def hyperfine_build_min_runs() -> str:
    return os.environ.get("BENCH_BUILD_MIN_RUNS", "5")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run hyperfine benchmarks for json-parser-compare.",
    )
    parser.add_argument(
        "--no-parse",
        action="store_true",
        help="Skip parse benchmarks (release CLI × fixtures). Default is to run parse.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run debug build benchmarks (hyperfine with `cargo clean` before each timed build).",
    )
    parser.add_argument(
        "--build-chart",
        action="store_true",
        help="Generate results/chart_build.png from build_results.json (does not run builds by itself).",
    )
    parser.add_argument(
        "--no-build-chart",
        action="store_true",
        help="With --build, skip generating the build chart even if build benchmarks ran.",
    )
    return parser.parse_args()


def cargo_env(repo_root: pathlib.Path) -> tuple[dict[str, str], pathlib.Path]:
    env = os.environ.copy()
    target = repo_root / "target"
    env["CARGO_TARGET_DIR"] = str(target)
    return env, target


def rustc_version() -> str:
    return subprocess.run(
        ["rustc", "--version"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()


def list_apps(repo_root: pathlib.Path) -> list[pathlib.Path]:
    examples_dir = repo_root / "examples"
    apps = sorted(p for p in examples_dir.glob("*-app") if p.is_dir())
    if not apps:
        print(f"error: no examples in {examples_dir}", file=sys.stderr)
        sys.exit(1)
    return apps


def run_parse_benchmarks(
    repo_root: pathlib.Path,
    cargo_env: dict[str, str],
    target: pathlib.Path,
    apps: list[pathlib.Path],
) -> None:
    fixtures_dir = repo_root / "fixtures"
    fixtures = sorted(fixtures_dir.glob("*.json"))
    if not fixtures:
        print(f"error: no fixtures in {fixtures_dir}", file=sys.stderr)
        sys.exit(1)

    extension = ".exe" if sys.platform in ("win32", "cygwin") else ""
    target_release = target / "release"

    print("Building release binaries (not timed)...")
    subprocess.run(
        ["cargo", "build", "--release"],
        cwd=repo_root,
        check=True,
        env=cargo_env,
    )

    results: list[dict] = []
    results_root = repo_root / "results"
    results_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        for example_path in apps:
            name = example_path.name.removesuffix("-app")
            if name in CHART_SKIP:
                print(f"Skipping parse benchmark for {name}-app (baseline)")
                continue

            bin_path = target_release / f"{example_path.name}{extension}"
            if not bin_path.exists():
                print(f"warning: missing binary {bin_path}, skipping", file=sys.stderr)
                continue

            for fixture in fixtures:
                fixture_rel = fixture.relative_to(repo_root)
                cmd = f"{bin_path} {fixture_rel}"
                export_path = tmp / f"{name}-{fixture.stem}.json"
                probe = subprocess.run(
                    [str(bin_path), str(fixture_rel)],
                    cwd=repo_root,
                    capture_output=True,
                    env=cargo_env,
                )
                if probe.returncode != 0:
                    print(
                        f"warning: {name} × {fixture.name} failed correctness check, skipping",
                        file=sys.stderr,
                    )
                    results.append(
                        {
                            "backend": name,
                            "fixture": fixture.stem,
                            "median_s": None,
                            "error": "parse failed on fixture",
                        }
                    )
                    continue

                print(f"hyperfine parse: {name} × {fixture.name}")
                subprocess.run(
                    [
                        "hyperfine",
                        f"--warmup={hyperfine_warmup()}",
                        f"--min-runs={hyperfine_min_runs()}",
                        f"--export-json={export_path}",
                        cmd,
                    ],
                    cwd=repo_root,
                    check=True,
                    env=cargo_env,
                )
                report = json.loads(export_path.read_text(encoding="utf-8"))
                results.append(
                    {
                        "backend": name,
                        "fixture": fixture.stem,
                        "median_s": report["results"][0]["median"],
                    }
                )

    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hostname": platform.node(),
        "os": platform.system(),
        "arch": platform.machine(),
        "rustc": rustc_version(),
        "benchmark": "parse",
        "method": "hyperfine",
        "note": "CLI parse: process + read file + parse (release binaries)",
        "fixtures": [f.stem for f in fixtures],
        "results": results,
    }

    out_path = results_root / "results.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


def run_build_benchmarks(
    repo_root: pathlib.Path,
    cargo_env: dict[str, str],
    apps: list[pathlib.Path],
) -> None:
    cpus = multiprocessing.cpu_count()
    results: list[dict] = []
    results_root = repo_root / "results"
    results_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        for example_path in apps:
            name = example_path.name.removesuffix("-app")
            if name in CHART_SKIP:
                print(f"Skipping build benchmark for {name}-app (baseline)")
                continue

            export_path = tmp / f"{name}-build.json"
            build_cmd = f"cargo build -j {cpus} --package {example_path.name}"
            print(f"hyperfine debug build: {example_path.name}")
            subprocess.run(
                [
                    "hyperfine",
                    "--warmup=1",
                    f"--min-runs={hyperfine_build_min_runs()}",
                    f"--export-json={export_path}",
                    "--prepare=cargo clean",
                    build_cmd,
                ],
                cwd=repo_root,
                check=True,
                env=cargo_env,
            )
            report = json.loads(export_path.read_text(encoding="utf-8"))
            results.append(
                {
                    "backend": name,
                    "median_s": report["results"][0]["median"],
                }
            )

    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hostname": platform.node(),
        "os": platform.system(),
        "arch": platform.machine(),
        "rustc": rustc_version(),
        "benchmark": "debug_build",
        "method": "hyperfine",
        "cpus": cpus,
        "note": "cargo clean && cargo build --package <name> (debug, not release)",
        "results": results,
    }

    out_path = results_root / "build_results.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


def generate_build_chart(repo_root: pathlib.Path) -> None:
    plot_script = repo_root / "scripts" / "plot_results.py"
    build_json = repo_root / "results" / "build_results.json"
    if not build_json.is_file():
        print(f"error: missing {build_json} (run ./bench.py --build first)", file=sys.stderr)
        sys.exit(1)
    subprocess.run(
        [
            sys.executable,
            str(plot_script),
            "--build",
            "--input",
            str(build_json),
            "--output",
            str(repo_root / "results" / "chart_build.png"),
        ],
        cwd=repo_root,
        check=True,
    )


def generate_parse_chart(repo_root: pathlib.Path) -> None:
    plot_script = repo_root / "scripts" / "plot_results.py"
    parse_json = repo_root / "results" / "results.json"
    if not parse_json.is_file():
        return
    subprocess.run(
        [
            sys.executable,
            str(plot_script),
            "--input",
            str(parse_json),
            "--output",
            str(repo_root / "results" / "chart.png"),
        ],
        cwd=repo_root,
        check=True,
    )


def main() -> None:
    args = parse_args()
    repo_root = pathlib.Path(__file__).resolve().parent

    # --build-chart alone: regenerate chart from existing build_results.json
    if args.build_chart and not args.build and not args.no_parse:
        generate_build_chart(repo_root)
        return

    do_parse = not args.no_parse
    do_build = args.build
    # Default ./bench.py: parse only, no build, no build chart
    if not args.no_parse and not args.build and not args.build_chart:
        do_parse = True
        do_build = False
        do_build_chart = False
    else:
        do_build_chart = args.build_chart or (args.build and not args.no_build_chart)

    if not do_parse and not do_build and not do_build_chart:
        print(
            "error: nothing to do (default: parse; or --build; or --build-chart)",
            file=sys.stderr,
        )
        sys.exit(2)

    if shutil.which("hyperfine") is None and (do_parse or do_build):
        print("error: hyperfine not found on PATH", file=sys.stderr)
        sys.exit(1)

    env, target = cargo_env(repo_root)
    apps = list_apps(repo_root)

    if do_parse:
        run_parse_benchmarks(repo_root, env, target, apps)
        generate_parse_chart(repo_root)

    if do_build:
        run_build_benchmarks(repo_root, env, apps)

    if do_build_chart:
        generate_build_chart(repo_root)


if __name__ == "__main__":
    main()
