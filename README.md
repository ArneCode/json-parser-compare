# JSON parser comparison

**AI assistance:** This document was drafted with AI assistance. The maintainer reviewed it. If anything looks wrong, please open an issue in your fork or upstream.

Compare Rust JSON parser examples (vendored from [parse-rosetta-rs](https://github.com/epage/parse-benchmarks-rs)) on shared fixtures, then plot parse times as a bar chart.

## Continuous integration

GitHub Actions ([`.github/workflows/benchmark.yml`](.github/workflows/benchmark.yml)) runs on pushes, pull requests, weekly schedule, and manual **workflow_dispatch**:

1. `cargo build --release` for all examples  
2. `./bench.py` (parse benchmarks only; no debug build timing in CI)  
3. Uploads `results/results.json` and `results/chart.png` as workflow artifacts  

Parse hyperfine defaults (local and CI): `--warmup=3` `--min-runs=10` (stricter than [parse-rosetta-rs](https://github.com/epage/parse-benchmarks-rs), which uses `1` and `5`). Override via `BENCH_WARMUP` / `BENCH_MIN_RUNS`.

## Prerequisites

- Rust toolchain (`cargo build --release`)
- [hyperfine](https://github.com/sharkdp/hyperfine) on `PATH` (e.g. `cargo install hyperfine`)
- Python 3 + matplotlib for the chart (`pip install -r scripts/requirements.txt`)

## Quick start

**Parse benchmarks only** (default):

```bash
./bench.py
```

Writes `results/results.json` and `results/chart.png`.

**Optional debug build benchmarks** (slow — runs `cargo clean` before each timed build):

```bash
./bench.py --build
```

Writes `results/build_results.json` and `results/chart_build.png`.

**Combine parse + build:**

```bash
./bench.py --build
```

(parse runs by default; add `--no-parse` to benchmark builds only.)

**Build benchmarks without generating the build chart:**

```bash
./bench.py --no-parse --build --no-build-chart
```

**Regenerate only the build chart** from existing `build_results.json`:

```bash
./bench.py --build-chart
# or: python3 scripts/plot_results.py --build
```

Outputs:

- `results/results.json` — median parse times per backend and fixture
- `results/chart.png` — parse bar chart
- `results/build_results.json` — median debug build time per backend (`--build`)
- `results/chart_build.png` — debug build bar chart (`--build`, or `--build-chart`)

## What is measured

**Parse** (default, via hyperfine): wall-clock per run of each release `*-app` binary with a fixture path argument. That includes process startup, reading the file, and parsing — the same shape as the upstream rosetta apps.

**Debug build** (optional `--build`): hyperfine on `cargo build --package <name>` with `--prepare=cargo clean` before each run, matching the upstream rosetta build benchmark style. Release binary size and release compile time are not measured.

Fixture (from [nativejson-benchmark](https://github.com/miloyip/nativejson-benchmark), same as upstream rosetta):

- `fixtures/canada.json` — large GeoJSON file

`bench.py` forces `CARGO_TARGET_DIR` to `./target` so release binaries are always next to the repo (even if your environment sets a global target dir).

`null-app` is built but excluded from the chart (it only reads the file, no parse).

### `marser-app` vs `marser-bare-app`

| Example | Role |
|---------|------|
| `marser-app` | Vendored rosetta grammar: recovery, `Invalid` values, rich error hooks (`try_insert_if_missing`, `if_error`, annotations). |
| `marser-bare-app` | Same AST shape without recovery or error-reporting matchers — closer to the other minimal JSON demos for timing. |

### Fixture compatibility

Only **`canada.json`** is benchmarked (matching upstream parse-rosetta-rs). `bench.py` skips a backend when the preflight parse exits non-zero. All vendored `*-app` examples currently pass `canada.json`; other nativejson files (e.g. `twitter.json`, `citm_catalog.json`) were dropped because several stock grammars fail on them (nom: `alphanumeric`-only string bodies; lalrpop/combine/grmtools: similar limits).

## Local `marser` development

By default `marser-app` and `marser-bare-app` use `marser = "0.1.3"` from crates.io. When working in the `parsing/` monorepo, you can patch to your tree in the workspace root `Cargo.toml`:

```toml
[patch.crates-io]
marser = { path = "../marser" }
```

## Refreshing vendored examples

Optional: copy from a local `parse-rosetta-rs` checkout with `scripts/vendor-from-rosetta.sh` (maintainer only; not required to build).
