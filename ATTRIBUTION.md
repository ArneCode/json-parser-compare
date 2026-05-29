# Attribution

Parser examples under `examples/*-app/` are vendored from [parse-rosetta-rs](https://github.com/epage/parse-benchmarks-rs) (also known as parse-rosetta-rs in this monorepo).

- **Upstream commit:** `0823dacb68162586fda4f53e04b0ef0deb60b1ec`
- **Fixtures** (`twitter.json`, `canada.json`, `citm_catalog.json`): from [nativejson-benchmark](https://github.com/miloyip/nativejson-benchmark) `data/`
- **`nom-app`:** parser strings diverge from upstream rosetta; see README “Deviations from parse-rosetta-rs” (based on nom [`examples/string.rs`](https://github.com/rust-bakery/nom/blob/main/examples/string.rs))

Respect upstream licenses of each parser crate listed in the corresponding `examples/<name>-app/Cargo.toml`.
