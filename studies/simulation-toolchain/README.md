# Simulation toolchain manifest example

This is a **software-only provenance example**, not an experiment, protocol recommendation, or biological result. It connects checked-in artifacts across the protocol compiler, media planner, oxygen solver, and calibration analysis repositories. Every source is explicitly labeled as a software fixture, simulation, or synthetic input; no physical calibration is claimed.

The artifact hashes in [`simulation-toolchain.json`](simulation-toolchain.json) are local-file hashes from the checked-out workspace. Tool revisions identify the checked-out Git versions used to create/check the example. Validate internal structure and cross-reference integrity with:

```bash
python3 studies/simulation-toolchain/validate.py
```

The validator infers the sibling workspace from this checkout, or accepts
`--workspace /path/to/workspace`. It requires `jsonschema` and checks file
hashes, portable paths, unique producers, and dependency order. The
software-only schema rejects physical-measurement claims. For a standalone
checkout, `--structure-only` checks the contract and explicitly reports that
artifact bytes were not verified. Unit tests verify byte checks in an isolated
temporary workspace without requiring sibling repositories.