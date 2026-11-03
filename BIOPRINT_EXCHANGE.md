# Bioprinting exchange (Phases F/G)

Personal hobby/learning project, AI-assisted. This adapter lets the local ResearchDesk
exchange research bundles with the offline Bioprinting Workbench. It is **not** an execution
bridge: import never calls `Desk.submit()`, never launches subprocesses and never contacts a
provider. Hashes attest byte integrity only; review status is software metadata and never
means scientific validation; imported bundles always stay publication-not-approved.

## Module (`tools/bioprint_exchange.py`)

Mirrors the Workbench contract (`bioprinting-workbench/docs/RESEARCH_EXCHANGE.md`, schema
`bioprinting-workbench/research-exchange/1`, bounds summarized in
`tools/schemas/bioprint-research-exchange-v1.json`):

- `validate_bundle` / `validate_hypothesis_card` / `validate_query_plan` /
  `validate_evidence_record` / `validate_foreign_model_run` / `validate_artifact_descriptor`:
  exact allowlists, bounded strings/arrays, 2–8 competing alternatives per hypothesis, closed
  and acyclic ancestry, prototype-pollution keys rejected.
- `verify_artifact_files(bundle, files)`: byte-counts then hashes exact bytes; flat safe
  basenames only; ≤ 10 MiB per file, ≤ 25 MiB total; no ZIP extraction, no URL fetch, no
  filesystem paths from callers.
- `preview_import(bundle, existing_records)` / `apply_import(bundle, existing_records)`:
  idempotent duplicates, conflicts block apply, apply constructs a new state (never a partial
  merge). `Desk.preview_bioprint_import` / `Desk.apply_bioprint_import` run these under the
  existing `RLock` with one atomic `save_store()` replacement; any failure restores the exact
  previous in-memory store (pinned by test).
- `to_desk_question(card)`: method-neutral question draft with `competing_hypotheses`; never
  writes to Desk, never touches the ectogenesis campaign contracts.
- `export_selected_results(selection, root)`: writes only explicitly selected result
  artifacts plus a canonical manifest under a generated flat directory; notes/caches are
  excluded by default.

## Routes (same-origin only, added beside the existing allowlist)

- `GET /api/bioprint/state` — the imported-bundle state.
- `POST /api/bioprint/preview` / `POST /api/bioprint/apply` — manifest ≤ 5 MiB (dedicated
  cap; the general 64 KB POST limit for other routes is unchanged). Same Host/Origin checks
  as every other Desk route.

## Cross-language digest rule

`canonical_json_bytes` uses sorted-key compact JSON with one trailing LF and matches the JS
implementation for portable-number values (golden vector `{"a":1,"b":2}` pinned on both
sides). For exchange/artifact integrity the rule is **exact producer bytes**; JS/Python float
formatting is never assumed identical. Shared fixtures live in
`tests/fixtures/bioprint_exchange/` (byte copies of the Workbench fixtures).

## Execution/result return (Phase G, mock-first)

Run/receipt records travel as `modelRuns` entries with statuses preserved verbatim
(`queued|running|succeeded|partial|failed|interrupted|submission-unknown` — an interrupted run
is never relabelled failed, and an ambiguous submission is `submission-unknown`, never
auto-retried). The Desk exchange panel submits a reviewed query plan only through the
existing local queue via an explicit user action; nothing here adds a provider adapter. A live
provider demonstration requires owner-supplied credentials and is a separate opt-in step.

## Tests

`tests/test_bioprint_exchange.py`: fixture validation parity, prototype/cycle/dangling
rejection, exact-byte artifact verification, idempotent preview/apply, conflict refusal,
verbatim receipt statuses, 2–8 question mapping, bounded result export with traversal
rejection, Desk import atomic rollback under injected save failure, and a `submit` call
counter that must stay zero during import. Run with
`python3 -B -m unittest discover -s tests -p 'test_bioprint_exchange.py' -v`.
