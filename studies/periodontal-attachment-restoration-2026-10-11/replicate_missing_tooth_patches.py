"""Additional-specimen transport check; frozen pilot settings, no tuning.

Run --prepare to acquire/audit sources and freeze plans, then --run separately.
Raw sources remain local. Source-derived outputs are CC BY-NC 4.0.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "derived" / "patch_replication"
SOURCES = ((88, "GLN04-289B-URM2", ">30", "F"),
           (90, "GLN05-292-URM2", "20-29", "F"))
SETTINGS = ("grid_spacing_mm", "center_fractions_xy", "patch_radii_mm",
            "support_inner_margin_mm", "support_outer_margin_mm", "methods",
            "minimum_support_points", "maximum_design_condition_number")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def load_benchmark():
    spec = importlib.util.spec_from_file_location("patch_replication_benchmark", HERE / "benchmark_missing_tooth_patches.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_plan(manifest, source, plan, pilot_bytes):
    """Reject source swaps and computational drift before evaluating targets."""
    pilot = json.loads(pilot_bytes)
    if (hashlib.sha256(pilot_bytes).hexdigest() != manifest["pilot_plan_sha256"]
            or manifest["settings"] != {key: pilot[key] for key in SETTINGS}
            or {key: plan[key] for key in SETTINGS} != manifest["settings"]):
        raise ValueError("Computational settings differ from frozen intake")
    if any(plan[key] != source[key] for key in ("model_id", "specimen_identifier", "archive_sha256")):
        raise ValueError("Source identity differs from frozen intake")
    if plan["source_model"] != f'M3#{source["model_id"]} {source["specimen_identifier"]}':
        raise ValueError("Source display label differs from frozen intake")


def prepare():
    benchmark = load_benchmark()
    reference = benchmark.reference
    pilot_bytes = (HERE / "patch_reconstruction_plan.json").read_text(encoding="utf-8").encode()
    pilot = json.loads(pilot_bytes)
    manifest = {"status": "frozen before new specimen patch outcomes; not independently preregistered",
        "development_specimen": 83, "pilot_plan_sha256": hashlib.sha256(pilot_bytes).hexdigest(),
        "selection": "all remaining Table1 adult maturation-H wear-1 specimens without dataset reconstructed-tip flag",
        "primary_doi": "10.1371/journal.pone.0159688", "dataset_doi": "10.18563/m3.2.1.e1",
        "settings": {key: pilot[key] for key in SETTINGS},
        "orientation": "source pose; no mirroring; fractional locations are computational, not homologous anatomical landmarks",
        "decision_rule": "report each specimen and all failures; no pooling patches as independent specimens; no retuning",
        "specimens": []}
    for model, identifier, age, sex in SOURCES:
        destination = reference.DEST / f"morphomuseum_M3_{model}.zip"
        url = f"https://www.morphomuseum.com/specimenfiles/send-file-specimenfile/{model}"
        if not destination.exists():
            with urlopen(Request(url, headers={"User-Agent": "regen-workbench/0.1"}), timeout=45) as response:
                raw = response.read(12000001)
            if len(raw) > 12000000 or not raw.startswith(b"PK"):
                raise ValueError("Unexpected or oversized source archive")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            sys.path.insert(0, str(ROOT / "tools"))
            import regen
            regen.record("dental-patch-replication-source-fetch", {"url": url,
                "doi": f"10.18563/m3.sf.{model}", "license": "CC-BY-NC-4.0"}, [destination])
        raw = destination.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        audits, poses, boundaries = {}, {}, {}
        with zipfile.ZipFile(destination) as archive:
            for role in ("OES", "EDJ"):
                base = f"M3#{model}/{identifier}_{role}"
                vertices, faces = reference.read_ply(archive.read(base + ".ply"))
                pose = reference.read_pose(archive.read(base + f"_M3_{model}.pos"))
                vertices = reference.transform(vertices, pose)
                audits[role], boundaries[role] = reference.mesh_audit(vertices, faces)
                poses[role] = pose
            readmes = [name for name in archive.namelist() if "read" in name.lower()]
            for name in readmes:
                print(model, name, archive.read(name).decode("utf-8", errors="replace"))
        import numpy as np
        if not np.allclose(poses["OES"], poses["EDJ"], rtol=0, atol=1e-10):
            raise ValueError("Paired meshes do not share their supplied pose")
        entry = {"model_id": model, "specimen_identifier": identifier,
            "age_years_source_table1": age, "sex_source_table1": sex,
            "maturation": "H", "wear_stage": 1, "reconstructed_tip_flag": False,
            "archive_bytes": len(raw), "archive_sha256": digest,
            "url": url, "doi": f"10.18563/m3.sf.{model}", "mesh_audits": audits,
            "shared_pose": True, "readme_members": readmes}
        manifest["specimens"].append(entry)
        plan = dict(pilot)
        plan.update({"model_id": model, "specimen_identifier": identifier,
            "source_model": f"M3#{model} {identifier}", "archive_sha256": digest,
            "analysis_type": "additional-specimen transport check with frozen pilot settings",
            "plan_status": manifest["status"]})
        target = OUT / f"M3_{model}" / "plan.json"
        if target.exists() and json.loads(target.read_text()) != plan:
            raise ValueError("Refusing to overwrite a different frozen plan")
        write_json(target, plan)
    path = OUT / "frozen_intake.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Refusing to overwrite a different frozen intake")
    write_json(path, manifest)
    print("Prepared frozen intake; no patch outcomes evaluated.")


def run():
    manifest = json.loads((OUT / "frozen_intake.json").read_text())
    benchmark = load_benchmark()
    pilot_bytes = (HERE / "patch_reconstruction_plan.json").read_text(encoding="utf-8").encode()
    results = []
    for source in manifest["specimens"]:
        model = source["model_id"]
        directory = OUT / f"M3_{model}"
        plan = json.loads((directory / "plan.json").read_text())
        validate_plan(manifest, source, plan, pilot_bytes)
        subprocess.run([sys.executable, str(HERE / "benchmark_missing_tooth_patches.py"),
            "--plan", str(directory / "plan.json"), "--out", str(directory),
            "--archive", str(benchmark.reference.DEST / f"morphomuseum_M3_{model}.zip")], check=True,
            stdout=subprocess.DEVNULL)
        summary = json.loads((directory / "patch_summary.json").read_text())
        means = {}
        for method in plan["methods"]:
            rows = [row for row in summary["rows"] if row["method"] == method]
            scored = [row for row in rows if row["status"] == "scored"]
            means[method] = {"scored": len(scored), "total": len(rows),
                "mean_patch_mae_mm": sum(row["mae_mm"] for row in scored) / len(scored) if scored else None}
        pairs = {}
        for row in summary["rows"]:
            pairs.setdefault(row["case_id"], {})[row["method"]] = row
        differences = []
        for case, rows in pairs.items():
            exterior = rows["exterior_quadratic"]["mae_mm"]
            informed = rows["internal_imaging_quadratic_residual"]["mae_mm"]
            differences.append({"case_id": case, "informed_minus_exterior_mae_mm":
                informed - exterior if informed is not None and exterior is not None else None})
        results.append({"model_id": model, "specimen_identifier": source["specimen_identifier"],
            "means": means, "quadratic_paired_differences": differences,
            "scored_comparisons": summary["scored_comparisons"]})
    write_json(OUT / "transport_summary.json", {"additional_specimens": len(results),
        "frozen_intake_sha256": hashlib.sha256((OUT / "frozen_intake.json").read_bytes()).hexdigest(),
        "independent_source_collections": 1, "results": results,
        "qualification": "same-collection transport check; no population inference or clinical margin"})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run"))
    args = parser.parse_args()
    prepare() if args.stage == "prepare" else run()
