from __future__ import annotations

import hashlib
import http.client
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen
import regen_desk as desk


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in (("DATA", self.root / "data"), ("CACHE", self.root / "cache"), ("PROV", self.root / "provenance")):
            patcher = patch.object(regen, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.desk = desk.Desk(self.root / "desk")
        self.addCleanup(lambda: self.desk.executor.shutdown(wait=True))

    def finish(self, request):
        job = self.desk.submit({"blueprint_id": "glycation", **request})
        self.desk.executor.shutdown(wait=True)
        return self.desk.run(job["id"])

    def test_partial_failure_preserves_real_snapshot_and_hashes(self):
        responses = [({"results": ["test snapshot"]}, [desk.hit("pubmed", "A study", "https://example.org/paper")]), desk.ProviderError("HTTP 429")]
        with patch.object(desk, "search_provider", side_effect=responses):
            run = self.finish({"kind": "search", "query": "carnosine", "providers": ["pubmed", "openalex"]})
        self.assertEqual(run["status"], "partial")
        self.assertEqual(len(run["result"]["hits"]), 1)
        path = self.desk.runs / run["id"]
        report = json.loads((path / "manifest.json").read_text())
        self.assertNotIn("run.json", report["outputs"])
        for file, metadata in report["outputs"].items():
            self.assertEqual(hashlib.sha256((path / file).read_bytes()).hexdigest(), metadata["sha256"])
        self.assertFalse((path / "openalex.json").exists())

    def test_all_provider_failures_are_not_success(self):
        with patch.object(desk, "search_provider", side_effect=desk.ProviderError("HTTP 403")):
            run = self.finish({"kind": "search", "query": "x", "providers": ["pubmed"]})
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["result"]["hits"], [])

    def test_anecdote_is_excluded_from_export_until_explicitly_included(self):
        self.desk.note({"blueprint_id": "glycation", "kind": "vendor claim", "direction": "supports", "claim": "Unverified claim", "url": "https://example.org/source"})
        reloaded = desk.Desk(self.desk.root)
        self.addCleanup(lambda: reloaded.executor.shutdown(wait=True))
        default_export = reloaded.export("glycation")
        self.assertEqual(default_export["notes"], [])
        self.assertTrue(default_export["notes_excluded"])
        note = reloaded.export("glycation", include_notes=True)["notes"][0]
        self.assertEqual(note["kind"], "vendor claim")
        self.assertEqual(note["review_status"], "unreviewed")

    def test_experiment_reader_shows_unavailable_organoid_assay_and_external_sources(self):
        result = self.desk.experiments()
        record = next(item for item in result["experiments"]
                      if item["experiment_id"] == "bonn-kidney-tubuloid-cyst-induction-imaging")
        self.assertEqual(record["validation_status"], "valid")
        self.assertEqual(record["assays"][0]["status"], "not_available")
        self.assertEqual(record["summary"]["tool"], "organoid-phenotyping")
        self.assertEqual(record["summary"]["n_manifest_rows"], 280)
        self.assertEqual(record["summary"]["n_pending_annotation_frames"], 280)
        self.assertEqual(record["developmental_context"]["stage_track"], "organoid_or_tissue_model")
        self.assertEqual(len(record["analysis_history"]), 3)
        self.assertEqual(record["current_analysis_by_kind"]["annotation_pilot"], "dede39dccb4cb6db")
        self.assertTrue(any(table["artifact_id"].startswith("phenotyping-measurements-")
                            for table in record["tables"]))
        self.assertFalse(next(item for item in record["artifacts"]
                              if item["id"] == "figure4-cyst-images")["local"])
        self.assertTrue(any(item["uri"] == "https://doi.org/10.60507/FK2/OM25XQ"
                            for item in record["artifacts"]))

    def test_campaign_evidence_is_typed_and_submission_context_is_frozen(self):
        data = {
            "blueprint_id": "reprogramming", "title": "LMNA positive control", "target": "LMNA",
            "hypothesis": "A known pathogenic variant affects vascular function.",
            "evidence": [{"axis_id": "tissue_function", "status": "source reports positive signal",
                          "value": "vasodilation restored", "unit": "qualitative", "comparator": "source control",
                          "timepoint": "in vitro", "source_url": "https://example.org/paper", "notes": "verify methods"}],
            "evidence_records": [
                {"axis_id": "tissue_function", "source_type": "publication", "source_title": "Primary paper",
                 "source_url": "https://example.org/paper", "species": "human", "stage_track": "adult vascular cells",
                 "developmental_interval": "in vitro assay", "model_system": "TEBV", "comparator": "unedited HGPS",
                 "outcome": "acetylcholine-evoked vasodilation", "measure": "percent diameter change",
                 "value": "reported group values", "unit": "%", "independent_unit": "donor",
                 "sample_size": "one HGPS donor", "follow_up": "study endpoint", "license": "CC BY 4.0",
                 "status": "source reports positive signal", "direction": "supports",
                 "notes": "No vessel-level IDs; donor-level generalization is unavailable."},
                {"axis_id": "tissue_function", "source_type": "dataset", "source_title": "Figure 8 data workbook",
                 "source_url": "https://example.org/dataset", "species": "human", "stage_track": "adult vascular cells",
                 "developmental_interval": "in vitro assay", "model_system": "TEBV", "comparator": "vehicle",
                 "outcome": "vasodilation", "measure": "percent diameter change", "value": "see source table",
                 "unit": "%", "independent_unit": "not recoverable", "sample_size": "35 vessel-summary values",
                 "follow_up": "week 3 and 5", "license": "CC0-1.0", "status": "source reports mixed signal",
                 "direction": "mixed", "dataset_sha256": "a" * 64, "notes": "Values do not identify independent donors."},
            ],
        }
        campaign = self.desk.campaign(data)
        self.assertEqual(campaign["evidence"][5]["status"], "source reports positive signal")
        self.assertEqual(len(campaign["evidence_records"]), 2)
        self.assertEqual(campaign["evidence_records"][0]["independent_unit"], "donor")
        self.assertNotEqual(campaign["evidence_records"][0]["record_id"], campaign["evidence_records"][1]["record_id"])
        self.assertIn("35 vessel-summary values", self.desk.export("reprogramming")["markdown"])
        with self.assertRaises(ValueError):
            self.desk.campaign({**data, "evidence": [{"axis_id": "tissue_function", "status": "proven efficacy"}]})
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.desk.campaign({**data, "evidence_records": [{**data["evidence_records"][0], "dataset_sha256": "not-a-hash"}]})
        with patch.object(self.desk.executor, "submit"):
            run = self.desk.submit({"blueprint_id": "reprogramming", "kind": "search", "query": "test", "providers": ["pubmed"], "campaign_id": campaign["id"]})
        saved_path = self.desk.runs / run["id"] / "submission.json"
        frozen = json.loads(saved_path.read_text())
        self.desk.campaign({**data, "id": campaign["id"], "title": "Edited campaign", "evidence": campaign["evidence"], "evidence_records": campaign["evidence_records"]})
        self.assertEqual(frozen["campaign"]["title"], "LMNA positive control")
        self.assertEqual(hashlib.sha256(saved_path.read_bytes()).hexdigest(), run["submission_sha256"])

    def test_dossier_links_hash_verified_experiment_artifacts(self):
        campaign = self.desk.campaign({
            "blueprint_id": "tissues", "title": "Organoid image workflow", "target": "kidney tubuloids",
            "hypothesis": "The source image workflow can support transparent, blinded morphology scoring.",
            "experiment_ids": ["bonn-kidney-tubuloid-cyst-induction-imaging"],
        })
        dossier = self.desk.export("tissues")
        self.assertEqual(dossier["linked_research"]["experiments"][0]["experiment_id"], campaign["experiment_ids"][0])
        archive = zipfile.ZipFile(io.BytesIO(self.desk.export_archive("tissues")))
        names = set(archive.namelist())
        self.assertIn("linked-research/experiments/bonn-kidney-tubuloid-cyst-induction-imaging/experiment.json", names)
        self.assertTrue(any("outputs/phenotyping-receipt-" in name for name in names))
        index = json.loads(archive.read("archive-index.json"))
        linked = next(row for row in index["files"] if "outputs/phenotyping-receipt-" in row["path"])
        self.assertEqual(linked["sha256"], hashlib.sha256(archive.read(linked["path"])).hexdigest())

    def test_dossier_links_receipt_verified_model_bundle_outputs(self):
        model_root=self.root / "model-bundles";bundle=model_root / "transport-fixture-01";bundle.mkdir(parents=True)
        input_bytes=b'{"fixture":"dimensionless"}\n'
        report_bytes=json.dumps({"schema_version":1,"result_kind":"dimensionless_two_compartment_transport",
            "biological_measurements":False,"physiologically_calibrated":False,"human_gestation_prediction":False,
            "limits":[],"outputs":{"final_core_state":0.2},"alternative_model":{"name":"one stock"},
            "assumptions":["dimensionless test fixture"]}).encode()+b"\n"
        (bundle/"input_config.json").write_bytes(input_bytes);(bundle/"transport_report.json").write_bytes(report_bytes)
        outputs={name:{"sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw)}
                 for name,raw in (("input_config.json",input_bytes),("transport_report.json",report_bytes))}
        (bundle/"receipt.json").write_text(json.dumps({"schema_version":1,"bundle_kind":"dimensionless_transport_theory",
            "package_version":"0.2.0","python_version":"3.12","input_sha256":outputs["input_config.json"]["sha256"],
            "implementation_sha256":{"pyproject.toml":"b"*64},"metadata":{},"outputs":outputs}),encoding="utf-8")
        with patch.object(desk,"ECTOGENESIS_MODEL_ROOT",model_root):
            self.desk.campaign({"blueprint_id":"tissues","title":"Transport fixture review","target":"exchange",
                "hypothesis":"Compare a dimensionless compartment model with a single-stock alternative.",
                "model_bundle_ids":["transport-fixture-01"]})
            dossier=self.desk.export("tissues")
            self.assertEqual(dossier["linked_research"]["model_bundles"][0]["bundle_kind"],"dimensionless_transport_theory")
            archive=zipfile.ZipFile(io.BytesIO(self.desk.export_archive("tissues")))
        receipt_name="linked-research/model-bundles/transport-fixture-01/receipt.json"
        report_name="linked-research/model-bundles/transport-fixture-01/transport_report.json"
        self.assertIn(receipt_name,archive.namelist());self.assertIn(report_name,archive.namelist())
        index=json.loads(archive.read("archive-index.json"))
        row=next(item for item in index["files"] if item["path"]==report_name)
        self.assertEqual(row["sha256"],hashlib.sha256(archive.read(report_name)).hexdigest())

    def test_campaign_starters_cover_repair_tissue_and_delivery(self):
        state = self.desk.state()
        for blueprint_id in ("reprogramming", "tissues", "nanomedicine"):
            self.assertTrue(state["campaign_starters"][blueprint_id])
            self.assertTrue(state["campaign_frameworks"][blueprint_id])
            self.assertTrue(state["campaign_starters"][blueprint_id][0]["reference_url"].startswith("https://"))

    def test_campaign_form_contains_every_renderer_field(self):
        class Forms(HTMLParser):
            def __init__(self):
                super().__init__()
                self.current = None
                self.fields = {}

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == "form":
                    self.current = attributes.get("id")
                    if self.current:
                        self.fields[self.current] = set()
                elif self.current and tag in {"input", "select", "textarea"}:
                    name = attributes.get("name")
                    if name:
                        self.fields[self.current].add(name)

            def handle_endtag(self, tag):
                if tag == "form":
                    self.current = None

        parser = Forms()
        parser.feed((Path(__file__).resolve().parents[1] / "tools" / "desk" / "index.html").read_text())
        self.assertTrue({
            "title", "target", "species", "tissue", "hypothesis", "endpoint", "falsifier",
            "evidence_stage", "study_design", "reference_url", "receptor", "structure_notes",
            "starter_id", "center_x", "center_y", "center_z", "size_x", "size_y", "size_z",
        } <= parser.fields["campaign-form"])
        self.assertIn("engine", parser.fields["docking-form"])

    def test_seed_migration_adds_and_prioritizes_areas_without_erasing_edits(self):
        self.desk.store["blueprints"] = [
            item for item in self.desk.store["blueprints"] if item["id"] not in {"tissues", "nanomedicine"}
        ]
        custom = next(item for item in self.desk.store["blueprints"] if item["id"] == "glycation")
        custom["question"] = "My saved question"
        self.desk.note({"blueprint_id": "glycation", "kind": "personal observation", "direction": "unclear", "claim": "Saved note"})
        self.desk.save_store()

        reloaded = desk.Desk(self.desk.root)
        self.addCleanup(lambda: reloaded.executor.shutdown(wait=True))
        ids = [item["id"] for item in reloaded.store["blueprints"]]
        self.assertEqual(ids[:3], ["reprogramming", "tissues", "nanomedicine"])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(next(item for item in reloaded.store["blueprints"] if item["id"] == "glycation")["question"], "My saved question")
        self.assertEqual(reloaded.store["notes"][0]["claim"], "Saved note")
        self.assertEqual(json.loads(reloaded.store_path.read_text())["blueprints"][1]["id"], "tissues")

    def test_curated_findings_reference_known_areas_and_https_urls(self):
        seeds = json.loads((desk.HOME / "config" / "research-blueprints.json").read_text(encoding="utf-8"))
        area_ids = [item["id"] for item in seeds["blueprints"]]
        self.assertEqual(set(seeds["focus_order"]), set(area_ids))
        self.assertEqual(len(area_ids), len(set(area_ids)))
        seen = set()
        priorities = set()
        for finding in seeds["findings"]:
            self.assertIn(finding["blueprint_id"], area_ids)
            self.assertTrue(finding["url"].startswith("https://"))
            identity = (finding["blueprint_id"], finding["title"])
            self.assertNotIn(identity, seen)
            seen.add(identity)
            if "priority" in finding:
                key = (finding["blueprint_id"], finding["priority"])
                self.assertNotIn(key, priorities)
                priorities.add(key)

    def test_invalid_note_source_and_blueprint_rejected(self):
        for data in ({"url": "javascript:alert(1)"}, {"kind": "proven efficacy"}, {"blueprint_id": "missing"}):
            with self.assertRaises(ValueError):
                self.desk.note({"blueprint_id": "glycation", "kind": "anecdote", "direction": "unclear", "claim": "x", **data})

    def test_unknown_actions_and_unbounded_search_rejected(self):
        for params in ({"kind": "shell"}, {"kind": "search", "query": "x", "providers": ["unknown"]}, {"kind": "search", "query": "x", "limit": 1000}, {"kind": "search", "query": "x", "limit": True}):
            with self.assertRaises(ValueError):
                self.desk.submit({"blueprint_id": "glycation", **params})

    def test_redacts_configured_keys_email_and_encoded_keys(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "fake+secret&token", "EMAIL": "private@example.org"}):
            result = desk.redact({"echo": "fake+secret&token private@example.org fake%2Bsecret%26token"})
        self.assertEqual(result["echo"], "[redacted] [redacted] [redacted]")

    def test_raw_network_errors_do_not_expose_keys(self):
        from urllib.error import HTTPError
        with patch.object(desk, "urlopen", side_effect=HTTPError("https://example.org/?api_key=secret", 401, "secret", {}, None)):
            with self.assertRaises(desk.ProviderError) as error:
                desk.fetch_json("https://example.org/?api_key=secret")
        self.assertNotIn("secret", str(error.exception))

    def test_trial_registration_is_not_reported_as_result(self):
        response = {"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT00000000", "briefTitle": "Trial"}, "statusModule": {"overallStatus": "COMPLETED"}}, "hasResults": False}]}
        with patch.object(desk, "fetch_json", return_value=response):
            _, rows = desk.search_provider("trials", "x", 2)
        self.assertFalse(rows[0]["has_results"])
        self.assertIn("not a result", rows[0]["evidence_type"])

    def test_restart_marks_pending_jobs_interrupted(self):
        path = self.desk.runs / ("a" * 32)
        path.mkdir()
        self.desk.save_run(path, {"id": "a" * 32, "status": "running"})
        reloaded = desk.Desk(self.desk.root, recover_pending=True)
        self.addCleanup(lambda: reloaded.executor.shutdown(wait=True))
        self.assertEqual(reloaded.run("a" * 32)["status"], "interrupted")

    def test_legacy_run_exposes_only_artifacts_that_exist(self):
        run_id = "a" * 32
        path = self.desk.runs / run_id
        path.mkdir()
        self.desk.save_run(path, {"id": run_id, "kind": "search", "status": "failed", "blueprint_id": "glycation", "created_utc": "2026-01-01T00:00:00Z"})
        self.assertEqual(self.desk.run(run_id)["artifacts"], {"submission.json": False, "manifest.json": False, "result.json": False})

    def test_read_only_desk_does_not_interrupt_another_worker(self):
        path = self.desk.runs / ("a" * 32)
        path.mkdir()
        self.desk.save_run(path, {"id": "a" * 32, "status": "running"})
        reader = desk.Desk(self.desk.root)
        self.addCleanup(lambda: reader.executor.shutdown(wait=True))
        self.assertEqual(reader.run("a" * 32)["status"], "running")

    def test_export_includes_runs_outside_display_window(self):
        for i in range(102):
            run_id = format(i, "032x")
            path = self.desk.runs / run_id
            path.mkdir()
            self.desk.save_run(path, {"id": run_id, "kind": "search", "status": "complete", "blueprint_id": "glycation", "created_utc": str(i).zfill(4)})
        self.assertEqual(len(self.desk.state()["runs"]), 100)
        self.assertEqual(len(self.desk.export("glycation")["runs"]), 102)

    def test_run_page_is_filterable_and_paginated(self):
        for i in range(65):
            run_id = format(i, "032x")
            path = self.desk.runs / run_id
            path.mkdir()
            self.desk.save_run(path, {"id": run_id, "kind": "search", "status": "complete", "blueprint_id": "glycation", "created_utc": str(i).zfill(4)})
        page = self.desk.run_page("glycation", offset=50, limit=10)
        self.assertEqual(page["total"], 65)
        self.assertEqual(page["offset"], 50)
        self.assertEqual(len(page["runs"]), 10)
        self.assertEqual(self.desk.run_page("tissues")["total"], 0)

    def test_archive_contains_snapshots_and_public_draft_but_excludes_notes_by_default(self):
        self.desk.note({"blueprint_id": "glycation", "kind": "personal observation", "direction": "unclear", "claim": "private detail"})
        response = {"results": [{"title": "Study", "url": "https://example.org/study"}]}
        with patch.object(desk, "search_provider", return_value=(response, [desk.hit("pubmed", "Study", "https://example.org/study")])):
            run = self.finish({"kind": "search", "query": "test", "providers": ["pubmed"]})
        archive = zipfile.ZipFile(io.BytesIO(self.desk.export_archive("glycation")))
        self.assertIn(f"runs/{run['id']}/pubmed.json", archive.namelist())
        self.assertIn(f"runs/{run['id']}/manifest.json", archive.namelist())
        self.assertIn("public_draft.md", archive.namelist())
        self.assertIn("archive-index.json", archive.namelist())
        self.assertNotIn("private detail", archive.read("dossier.json").decode())
        self.assertNotIn("private detail", archive.read("public_draft.md").decode())

    def test_pubchem_uses_stereo_smiles_and_records_rdkit_version(self):
        if not importlib.util.find_spec("rdkit"):
            self.skipTest("RDKit is optional")
        raw = {"PropertyTable": {"Properties": [{"CID": 1, "SMILES": "N[C@@H](C)C(=O)O", "ConnectivitySMILES": "NC(C)C(=O)O", "Title": "Fixture"}]}}
        with patch.object(desk, "fetch_json", return_value=raw):
            run = self.finish({"kind": "compound", "name": "fixture"})
        self.assertEqual(run["status"], "complete", run.get("error"))
        self.assertIn("@", run["result"]["molecules"][0]["smiles"])
        self.assertTrue(run["result"]["rdkit_version"])

    def test_http_artifacts_and_origin_and_path_containment(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), desk.make_handler(self.desk))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        self.addCleanup(connection.close)
        run_dir = self.desk.runs / ("b" * 32)
        run_dir.mkdir()
        (run_dir / "result.json").write_text('{"ok":true}')
        connection.request("GET", f"/api/artifact/{run_dir.name}/result.json")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read()), {"ok": True})
        connection.request("GET", "/api/runs?blueprint_id=glycation&offset=0&limit=5")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read())["total"], 0)
        connection.request("GET", "/api/export/glycation.zip")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "application/zip")
        self.assertTrue(response.read().startswith(b"PK"))
        for method, path, headers in [("POST", "/api/blueprints", {"Content-Type": "application/json", "Origin": "https://malicious.example"}), ("GET", "/api/state", {"Host": "malicious.example"}), ("GET", "/api/artifact/../../workspace.json", {})]:
            connection.request(method, path, body='{}' if method == 'POST' else None, headers=headers)
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()


@unittest.skipUnless(importlib.util.find_spec("rdkit"), "RDKit is optional in the dev image")
class ChemistryTests(unittest.TestCase):
    setUp = DeskTests.setUp
    finish = DeskTests.finish
    def test_stereochemistry_identity_and_similarity(self):
        from rdkit import Chem
        left = desk.molecule("N[C@@H](C)C(=O)O")
        right = desk.molecule("N[C@H](C)C(=O)O")
        row = desk.describe(left, left)
        self.assertIn("@", row["smiles"])
        self.assertEqual(row["similarity"], 1)
        self.assertLess(desk.describe(right, left)["similarity"], 1)
        self.assertEqual(Chem.MolToSmiles(left), row["smiles"])

    def test_generated_graphs_are_distinct_valid_and_preserve_stereo(self):
        from rdkit import Chem
        parent = desk.molecule("N[C@@H](Cc1ccccc1)C(=O)O")
        variants = desk.enumerate_variants(parent)
        self.assertGreater(len(variants), 0)
        smiles = [Chem.MolToSmiles(m) for m, _ in variants]
        self.assertEqual(len(smiles), len(set(smiles)))
        self.assertNotIn(Chem.MolToSmiles(parent), smiles)
        for s in smiles:
            self.assertIn("@", s)
            self.assertIsNotNone(desk.molecule(s))
        self.assertEqual(desk.enumerate_variants(desk.molecule("CCO")), [])

    def test_rejects_disconnected_invalid_and_oversized_inputs(self):
        for smiles in ("not-a-smiles", "CC.O", "C" * 101):
            with self.assertRaises(ValueError):
                desk.molecule(smiles)

    def test_real_conformer_run_hashes_and_relative_energy(self):
        run = self.finish({"kind": "conformers", "smiles": "CCO", "conformers": 2, "seed": 42})
        self.assertEqual(run["status"], "complete", run.get("error"))
        compound = run["result"]["compounds"][0]
        self.assertEqual(compound["conformers_converged"], 2)
        self.assertEqual(min(c["relative_energy_kcal_mol"] for c in compound["conformers"]), 0)
        path = self.desk.runs / run["id"]
        report = json.loads((path / "manifest.json").read_text())
        self.assertIn("conformers/manifest.json", report["outputs"])
        for file, meta in report["outputs"].items():
            self.assertEqual(hashlib.sha256((path / file).read_bytes()).hexdigest(), meta["sha256"])

    def test_property_gate_retains_rejected_variants(self):
        run = self.finish({"kind": "variants", "smiles": "c1ccccc1", "max_mw": 50, "max_tpsa": 0})
        self.assertEqual(run["status"], "complete", run.get("error"))
        self.assertGreater(len(run["result"]["molecules"]), 1)
        self.assertTrue(all(not r["passes_constraints"] for r in run["result"]["molecules"]))


if __name__ == "__main__":
    unittest.main()
