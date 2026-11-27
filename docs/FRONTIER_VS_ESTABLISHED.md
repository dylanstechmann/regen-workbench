# Frontier versus established

**2026-11-27**

This note separates reproducible Research Desk software behavior from scientific
questions that remain open. The checks below were agent-run against local,
explicitly curated files and synthetic fixtures.

## Established software behavior

- The dependency-equipped full Python suite completed **945 tests**, with **100
  declared optional-dependency skips** and no failures or errors.
- Offline catalog comparison visibly reports old and new metadata values while
  matching entries and artifacts by stable IDs.
- In a temporary copy, a one-byte artifact mutation with unchanged declared byte
  size and SHA-256 was rejected by the local public-edition builder **before any
  output directory was created**. The catalog metadata diff remained separate
  from that publication-integrity gate.
- Synthetic bioprinting intake verified its declared local artifact, previewed
  six records without conflicts, and left the Desk store unchanged. Preview does
  not apply records or publish them.

These results support reproducible software integrity and curation behavior.
They do not upgrade the evidence label of any linked research artifact.

## Frontier and not established

- Source quality, source-to-conclusion linkage, and biological validity of the
  curated research remain separate scientific-review questions.
- File hashes, metadata diffs, synthetic intake, and passing software tests do
  not establish scientific review or independent biological replication.
- Docker and `regen doctor` were unavailable in this environment; no container
  health or provider readiness result is claimed.
- No clinical benefit, tissue regeneration, rejuvenation, or durable youthful
  function is established by these checks.

## Update when evidence changes

Update this note whenever a new result changes one of these boundaries. Record
exact commands, source revisions, environment and skips for software changes.
For scientific changes, identify the independently reviewed source, biological
unit, measured endpoint and limitations; do not substitute a software receipt
for that evidence. Record Docker or `regen doctor` status only after actually
running it in a compatible environment.
