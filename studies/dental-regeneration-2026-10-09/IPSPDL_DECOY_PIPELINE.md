# iPS-PDL reference sensitivity: reproducible pipeline

This pipeline re-quantifies the same nine PRJDB39888 libraries against the unchanged GENCODE v50 transcript targets with full GRCh38.p14 genomic decoys. It measures reference sensitivity of the earlier exploratory estimates. Decoy-aware estimates are not a ground-truth phenotype or a functional regeneration result.

## Bound reference and runtime

The [reference receipt](ipspdl_rnaseq_decoy_reference_receipt.json) records the actual download and preparation: 897,322,567 compressed genome bytes, publisher MD5 `780c013e525df4fcbe8ef85644f5e37c`, SHA-256 `3c28e7bcc390d40970455c657565799ed37c2146c26beebb96e8fd729405e93a`. The full assembly includes alternate/patch sequences. Its 706 FASTA records are appended as genomic decoys after the 670,670 unchanged transcript targets. The gentrome preserves complete pipe-delimited GENCODE identifiers; concatenated gzip members and source terminal newlines preserve FASTA record boundaries.

The transcript SHA-256 remains `5a320f524d73b5793518eb19b118829033713443d0f42af20a67bb31cc06cf56`, matching the [baseline reference receipt](ipspdl_rnaseq_reference_receipt.json). Publisher checksums, bounded HTTP ranges, gzip integrity, identifier uniqueness/collisions, ordering and resulting file hashes are checked by [prepare_ipspdl_decoy_reference.py](prepare_ipspdl_decoy_reference.py). Range pieces and resumed prefixes are provisional until the assembled publisher checksum passes.

The baseline and candidate use the same locally installed Salmon 2.7.0 implementation and [RNA-seq container recipe](rnaseq.Dockerfile). The local image ID is `sha256:ba1247ab03b2f21d4dcfaa003d00b0a21c31f0efa5d96ad76e59735be9a49ab7`. The index retains duplicate transcript targets with `--keepDuplicates`, preserving the baseline target set; it uses the installed binary's `--ramLimit 4` sort-memory setting. This setting is not a guarantee that the entire process stays within 4 GiB. The documented run also limits the container to 24 GiB and at most two quantifications at a time, each with eight threads.

The [Salmon documentation](https://salmon.readthedocs.io/en/latest/salmon.html) recommends genomic decoys to reduce spurious transcript matches and describes concatenating the full genome. That documentation currently identifies its branch as 1.12.0. The local 2.7.0 binary's supported options and produced metadata govern this execution; the versions are not assumed to have identical implementation details. No unsupported `--sparse` or header-truncating `--gencode` option is added.

## Execute from the repository root

The workbench and the 17 staged seekable gzip FASTQs must already exist. Raw DDBJ inputs, indexes, temporary files and full quantification tables stay in ignored `data/` storage. The preparation step performs a real source fetch through `regen` and creates a provenance receipt.

```powershell
docker build -t regen-ipspdl-rnaseq:1 -f studies/dental-regeneration-2026-10-09/rnaseq.Dockerfile studies/dental-regeneration-2026-10-09
docker compose exec -T workbench python /lab/workbench/studies/dental-regeneration-2026-10-09/prepare_ipspdl_decoy_reference.py
docker run --rm --name regen-ipspdl-decoy-batch --memory 24g -e THREADS=8 -e MAX_PARALLEL=2 -v "${PWD}/data:/data" -v "${PWD}/studies/dental-regeneration-2026-10-09:/work" regen-ipspdl-rnaseq:1 python /work/run_ipspdl_decoy_rnaseq.py
```

Rebuilding the image may resolve a later package build; compare the actual binary version and image identity with the recorded execution before interpreting a rerun. The environment file records requested versions rather than claiming that a future image rebuild will have the same image digest.

[run_ipspdl_decoy_rnaseq.py](run_ipspdl_decoy_rnaseq.py) checks reference hashes and index boundaries before quantification. It uses the existing manifest's eight paired runs and one single/layout-unspecified run. Automatic library-type detection, sequence-bias and GC-bias correction match the baseline. Per-run bindings include staged input hashes, command, driver, manifest, version and reference receipt. Successful completion additionally requires Salmon's explicit complete/converged flags and an empty error list.

An unchanged completed result can be resumed only after validating its binding, quantification hash, metadata hash and embedded metadata. Existing incomplete or differently bound output is preserved and refused. An interrupted index also cannot be silently reused. Inspect preserved logs and retain the failed attempt before choosing a separate recovery output; the script does not erase data to make a rerun look clean.

## Compare complete estimates

```powershell
docker compose exec -T workbench python /lab/workbench/studies/dental-regeneration-2026-10-09/compare_ipspdl_quantification.py --manifest /lab/workbench/studies/dental-regeneration-2026-10-09/ipspdl_rnaseq_manifest.tsv --gtf /lab/data/literature/gencode-v50/gencode.v50.annotation.gtf.gz --transcripts /lab/data/literature/gencode-v50/gencode.v50.transcripts.fa.gz --baseline-dir /lab/data/structures/ipspdl-rnaseq/quant --candidate-dir /lab/data/structures/ipspdl-rnaseq/quant-decoy --baseline-reference-manifest /lab/workbench/studies/dental-regeneration-2026-10-09/ipspdl_rnaseq_reference_receipt.json --candidate-reference-manifest /lab/workbench/studies/dental-regeneration-2026-10-09/ipspdl_rnaseq_decoy_reference_receipt.json --out-dir /lab/data/structures/ipspdl-rnaseq/sensitivity
```

The comparison rejects incomplete estimates, missing/extra libraries, changed target names or lengths, inconsistent indexes, changed read basenames and unequal processed-fragment totals. File hashes retain the exact compared outputs. Historical baseline input-payload identity still depends on the earlier download/staging provenance; matching names and fragment totals alone are not a proof of byte identity at the baseline execution time.

Outputs include marker TPM and group summaries, mapping/decoy diagnostics, correlations over genes expressed in either version, and descriptive PCA with fixed baseline features or independently reselected features. TPM is compositional, so reassigning some fragments can also change other TPM values. PCA coordinates are arbitrary up to rotations and signs; the report uses geometric agreement rather than treating a sign change as biology.

All-nine and paired-only scopes are separate. Removing DRR913336 leaves two primary-PDL labels versus three in the other groups and removes a donor together with its layout; it cannot isolate a pure library-layout effect. The iPS-PDL products share one parental iPSC background and lack a verified conditioned-medium-source crosswalk. No donor-level significance, identity score, clinical threshold or aging effect is qualified. Native single-cell deposited-entry cp10k values retain their own denominators and are not merged with bulk TPM.

## Verification

The complete host regression suite passed 446 tests (43 optional-dependency skips). The scientific container passed 55 focused checks covering native matrices/markers, reference construction, run integrity and comparison behavior. A baseline-against-itself smoke on all nine actual libraries reproduced unchanged mapping/markers and the earlier PCA; it verifies plumbing, not a decoy result.

```powershell
docker run --rm --entrypoint python -v "${PWD}:/repo:ro" -w /repo regen-workbench:local -m unittest discover -s tests -p 'test_ipspdl_*.py' -v
```

Actual decoy results require the completed run receipt and the separately generated sensitivity report. This methods document does not substitute for those outcomes.
