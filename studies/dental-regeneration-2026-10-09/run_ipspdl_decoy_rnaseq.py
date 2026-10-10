"""Build a bounded-memory decoy index and quantify the same nine source libraries."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

DATA, HERE = Path("/data/structures/ipspdl-rnaseq"), Path("/work")
INDEX = DATA / "gencode-v50-full-genome-decoy"
OUT = DATA / "quant-decoy"
REF = DATA / "decoy-reference"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def complete_metadata(metadata: dict) -> bool:
    return (metadata.get("meta_info_complete") is True
            and metadata.get("em_converged") is True
            and metadata.get("quant_errors") == [])


def run_command(row: dict, threads: int) -> tuple[list[str], list[Path]]:
    run = row["run"]
    command = ["salmon", "quant", "--index", str(INDEX), "--libType", "A", "--threads", str(threads),
               "--seqBias", "--gcBias", "--output", str(OUT / run)]
    if row["layout"] == "paired":
        inputs = [DATA / "gzip-inputs" / f"{run}_1.fastq.gz", DATA / "gzip-inputs" / f"{run}_2.fastq.gz"]
        command += ["--mates1", str(inputs[0]), "--mates2", str(inputs[1])]
    elif row["layout"] == "single/unspecified":
        inputs = [DATA / "gzip-inputs" / f"{run}.fastq.gz"]
        command += ["--unmatedReads", str(inputs[0])]
    else:
        raise ValueError(f"Unsupported layout for {run}")
    return command, inputs


def reuse_completed(output: Path, binding: dict) -> dict:
    receipt_file = output / "runner_receipt.json"
    if not receipt_file.is_file():
        raise ValueError(f"Existing output has no completed receipt: {output}")
    record = json.loads(receipt_file.read_text())
    if record.get("binding") != binding or record.get("status") != "completed":
        raise ValueError(f"Existing output has a different binding or did not complete: {output}")
    if sha(output / "quant.sf") != record.get("quant_sha256"):
        raise ValueError(f"Existing quantification bytes differ: {output}")
    metadata_path = output / "aux_info" / "meta_info.json"
    metadata = json.loads(metadata_path.read_text())
    if (sha(metadata_path) != record.get("metadata_sha256")
            or not complete_metadata(metadata) or record.get("metadata") != metadata):
        raise ValueError(f"Existing output metadata differs or did not converge: {output}")
    return record


def quantify(row: dict, threads: int, shared_binding: dict) -> dict:
    run, output = row["run"], OUT / row["run"]
    command, inputs = run_command(row, threads)
    input_info = [{"filename": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in inputs]
    binding = {**shared_binding, "command": command, "inputs": input_info}
    if output.exists():
        record = reuse_completed(output, binding)
        print(f"Reused hash-verified completed {run}", flush=True)
        return record
    record = {"run": run, "sample": row["sample_name"], "layout": row["layout"], "binding": binding,
              "started_utc": now()}
    print(f"Quantifying {run}: {row['layout']}", flush=True)
    with (OUT / f"{run}.log").open("w") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    record["exit_code"] = completed.returncode
    metadata_path = output / "aux_info" / "meta_info.json"
    if completed.returncode == 0 and (output / "quant.sf").is_file() and metadata_path.is_file():
        record["quant_sha256"] = sha(output / "quant.sf")
        record["metadata_sha256"] = sha(metadata_path)
        record["metadata"] = json.loads(metadata_path.read_text())
        record["status"] = "completed" if complete_metadata(record["metadata"]) else "failed"
    else:
        record["status"] = "failed"
    record["finished_utc"] = now()
    if output.exists():
        (output / "runner_receipt.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{record['status']} {run}: {record.get('metadata', {}).get('percent_mapped')}% mapped", flush=True)
    return record


def main() -> None:
    reference_path = HERE / "ipspdl_rnaseq_decoy_reference_receipt.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    gentrome, decoys = REF / "gentrome.fa.gz", REF / "decoys.txt"
    if sha(gentrome) != reference["reference"]["gentrome_sha256"] or sha(decoys) != reference["reference"]["decoys_sha256"]:
        raise ValueError("Decoy reference bytes differ from receipt")
    manifest = HERE / "ipspdl_rnaseq_manifest.tsv"
    with manifest.open(encoding="utf-8", newline="") as inp:
        samples = list(csv.DictReader(inp, delimiter="\t"))
    if {row["run"] for row in samples} != {f"DRR913{n}" for n in range(328, 337)} or len(samples) != 9:
        raise ValueError("Expected exact nine-library source manifest")
    threads = int(os.environ.get("THREADS", "8"))
    parallel = int(os.environ.get("MAX_PARALLEL", "1"))
    if threads < 1 or threads > 16 or parallel not in (1, 2):
        raise ValueError("THREADS must be 1..16; MAX_PARALLEL must be 1 or 2")
    version = subprocess.check_output(["salmon", "--version"], text=True).strip()
    OUT.mkdir(parents=True, exist_ok=True)
    index_command = ["salmon", "index", "--transcripts", str(gentrome), "--decoys", str(decoys),
                     "--index", str(INDEX), "--threads", str(threads), "--ramLimit", "4", "--keepDuplicates"]
    index_binding = DATA / "decoy_index_binding.json"
    binding = {"reference_receipt_sha256": sha(reference_path), "command": index_command, "salmon_version": version}
    if INDEX.exists():
        if not index_binding.is_file() or json.loads(index_binding.read_text()) != binding or not (INDEX / "index.ssi").is_file():
            raise ValueError("Existing decoy index is incomplete or has a different binding")
    else:
        print("Building full-genome decoy index (sshash sort RAM ceiling 4 GiB)", flush=True)
        with (DATA / "decoy_index.log").open("w") as log:
            subprocess.run(index_command, stdout=log, stderr=subprocess.STDOUT, check=True)
        index_binding.write_text(json.dumps(binding, indent=2) + "\n")
    info = json.loads((INDEX / "info.json").read_text())
    if (info["num_decoys"] != reference["reference"]["decoy_records"]
            or info["num_refs"] != reference["reference"]["transcript_records"] + reference["reference"]["decoy_records"]
            or info["first_decoy_index"] != reference["reference"]["transcript_records"]
            or not info.get("keep_duplicates")):
        raise ValueError("Index does not preserve requested decoys and duplicate transcript targets")
    receipt = {"schema_version": 1, "started_utc": now(), "salmon_version": version,
               "driver_sha256": sha(Path(__file__)), "manifest_sha256": sha(manifest),
               "reference_receipt_sha256": sha(reference_path), "index_command": index_command,
               "index_info": info, "index_log_sha256": sha(DATA / "decoy_index.log"),
               "index_binding_sha256": sha(index_binding), "threads_per_run": threads, "max_parallel": parallel,
               "runs": [], "status": "running"}
    receipt_path = HERE / "ipspdl_decoy_run_receipt.json"
    shared_binding = {key: receipt[key] for key in ("salmon_version", "driver_sha256", "manifest_sha256", "reference_receipt_sha256")}
    failures = []
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        pending = {executor.submit(quantify, row, threads, shared_binding): row["run"] for row in samples}
        for future in as_completed(pending):
            run = pending[future]
            try:
                record = future.result()
            except Exception as exc:
                record = {"run": run, "status": "failed", "error": str(exc)}
            receipt["runs"].append(record)
            receipt["runs"].sort(key=lambda row: row["run"])
            if record["status"] != "completed":
                failures.append(run)
                for queued in pending:
                    queued.cancel()
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    if failures:
        receipt.update(status="failed", finished_utc=now())
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        raise RuntimeError(f"Incomplete Salmon batch {failures}; outputs and logs preserved")
    receipt.update(status="completed", finished_utc=now())
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
