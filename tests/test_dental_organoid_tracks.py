"""New default-area migration and typed campaign scopes; no biological tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen_desk as desk


class DentalOrganoidTracks(unittest.TestCase):
    def test_seed_migration_preserves_saved_question_and_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            first = desk.Desk(Path(directory))
            first.executor.shutdown(wait=True)
            first.store["blueprints"] = [p for p in first.store["blueprints"] if p["id"] not in {"dental","organoids"}]
            first.store["blueprints"][0]["question"] = "Saved user question"
            first.store["notes"] = [{"claim":"Saved observation"}]
            first.save_store()
            second = desk.Desk(Path(directory))
            self.addCleanup(lambda: second.executor.shutdown(wait=True))
            self.assertEqual(second.store["blueprints"][0]["question"],"Saved user question")
            self.assertEqual(second.store["notes"],[{"claim":"Saved observation"}])
            ids = [p["id"] for p in second.store["blueprints"]]
            self.assertIn("dental",ids)
            self.assertIn("organoids",ids)
            self.assertEqual(len(ids),len(set(ids)))

    def test_campaign_evidence_axes_and_scopes_are_explicit(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        for key, count in [("dental",8),("organoids",3)]:
            axes = {axis["id"] for axis in seeds["campaign_frameworks"][key]}
            starters = seeds["campaign_starters"][key]
            self.assertEqual(len(starters),count)
            self.assertEqual(len({s["id"] for s in starters}),count)
            for s in starters:
                for field in ("hypothesis","endpoint","falsifier","evidence_stage","study_design","structure_notes"):
                    self.assertTrue(s[field].strip())
                self.assertTrue(s["reference_url"].startswith("https://"))
                for e in s["evidence"]:
                    self.assertIn(e["axis_id"],axes)
                    self.assertIn(e["status"],desk.EVIDENCE_STATUS)
        periodontal = next(s for s in seeds["campaign_starters"]["dental"] if s["id"]=="periodontal-controlled-contrasts")
        attachment_summary = next(e for e in periodontal["evidence"] if e["axis_id"]=="attachment")
        self.assertEqual(attachment_summary["status"],"source reports mixed signal")
        self.assertIn("1.905 mm", attachment_summary["value"])
        self.assertIn("no significant between-group CAL", attachment_summary["value"])
        self.assertIn("no significant",periodontal["structure_notes"])

    def test_ips_pdl_starter_preserves_iPSC_line_and_batch_scope(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "ips-pdl-cell-function")
        self.assertEqual(len(starter["evidence_records"]), 2)
        source_record = starter["evidence_records"][0]
        self.assertIn("same iPSC line", source_record["independent_unit"])
        self.assertIn("batch #1", starter["structure_notes"])
        graft_record = starter["evidence_records"][1]
        self.assertIn("subcutaneous", graft_record["model_system"])
        self.assertIn("not stated", graft_record["sample_size"].lower())
        self.assertIn("load transfer", graft_record["notes"].lower())
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "dental", "id": ""})
            self.assertEqual(saved["evidence_records"][0]["independent_unit"], source_record["independent_unit"])
            self.assertIn("One iPSC line", saved["evidence_records"][0]["sample_size"])

    def test_orthotopic_rat_starter_keeps_ankylosis_and_animal_denominator(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "ips-bmp6-rat-periodontal-defect")
        record = starter["evidence_records"][0]
        self.assertIn("n=4/group", record["sample_size"])
        self.assertIn("ankylosis", record["notes"].lower())
        self.assertIn("iPSCs-only", record["comparator"])
        self.assertEqual(record["status"], "source reports mixed signal")

    def test_root_preseeding_starter_keeps_timing_conflict_and_nested_denominator(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "pdl-progenitor-root-preseed-replant")
        record = starter["evidence_records"][0]
        self.assertIn("four athymic nude rats", record["sample_size"].lower())
        self.assertIn("eight molars", record["sample_size"].lower())
        self.assertIn("six months", record["follow_up"].lower())
        self.assertIn("six weeks", record["follow_up"].lower())
        self.assertIn("no direct mobility", record["notes"].lower())
        self.assertEqual(record["status"], "source reports positive signal")

    def test_usag1_starter_keeps_animal_adverse_signals_and_human_trial_boundary(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        source_seeds = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/desk_seeds.json").read_text(encoding="utf-8"))
        dossier = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/usag1_translation_review.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "usag1-developmental-tooth-activation")
        source_starter = next(s for s in source_seeds["campaign_starters"]["dental"] if s["id"] == starter["id"])
        self.assertEqual(starter["evidence_records"], dossier["evidence_records"])
        self.assertEqual(source_starter["evidence_records"], dossier["evidence_records"])
        self.assertEqual(len(starter["evidence_records"]), 4)
        axes = [item["axis_id"] for item in starter["evidence"]]
        self.assertEqual(len(axes), len(set(axes)))
        control = next(item for item in starter["evidence"] if item["axis_id"] == "control")
        self.assertEqual(control["status"], "not assessed")
        self.assertIn("recruitment as Complete", control["value"])
        receipt = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/usag1_translation_receipt.json").read_text(encoding="utf-8"))
        self.assertEqual({row["id"] for row in receipt["records"]}, {"PMC7880588", "TRG035-Phase-IIa-2026-08-17", "TRG035-news-index-2026-10-10", "jRCT2051240154", "PMID42218011"})
        self.assertTrue(all(row["status"] == "retrieved_and_identity_checked" for row in receipt["records"]))
        animal = starter["evidence_records"][0]
        self.assertIn("not TRG035", animal["model_system"])
        self.assertIn("immunosuppression", animal["value"])
        self.assertEqual(animal["status"], "source reports mixed signal")
        phase_one = starter["evidence_records"][1]
        self.assertIn("Complete", phase_one["value"])
        self.assertIn("no trial results are posted", phase_one["value"])
        self.assertIn("no tooth-formation endpoint", phase_one["measure"])
        self.assertIn("legacy", phase_one["notes"])
        phase_two = starter["evidence_records"][2]
        self.assertIn("Target n=24", phase_two["sample_size"])
        self.assertIn("planned after review by the trial-site IRB", phase_two["notes"])
        imaging = starter["evidence_records"][3]
        self.assertIn("0-25 days", imaging["developmental_interval"])
        self.assertIn("human surrogate", imaging["notes"])
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "dental", "id": ""})
            saved_records = [{key: value for key, value in record.items() if key != "record_id"}
                             for record in saved["evidence_records"]]
            self.assertEqual(saved_records, dossier["evidence_records"])
            self.assertEqual(len({record["record_id"] for record in saved["evidence_records"]}), 4)

    def test_ko_archive_audit_traces_sra_samples_without_assigning_clones(self):
        audit = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/geo_archive_metadata_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(len(audit["records"]), 4)
        self.assertFalse(audit["qualification"]["clone_to_sample_mapping_found"])
        self.assertFalse(audit["qualification"]["differentiation_batch_mapping_found"])
        records = {item["record"]["accession"]: item["record"] for item in audit["records"]}
        self.assertEqual(records["SRX30400800"]["geo_sample_identifier"], "GSM9224212")
        self.assertEqual(records["SRX30400800"]["sra_sample_accession"], "SRS26437414")
        self.assertEqual(records["SRX30400800"]["instrument_model"], "NextSeq 2000")
        attributes = {item["name"]: item["value"] for item in records["SAMN51222981"]["attributes"]}
        self.assertEqual(attributes["genotype"], "DLX3 knockout")
        self.assertEqual(attributes["treatment"], "C3-DLL4")

    def test_fulltext_observations_roundtrip_with_outcome_specific_intervals(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        authored = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/endpoint_review.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "periodontal-controlled-contrasts")
        self.assertEqual(starter["evidence_records"], authored["evidence_records"])
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "dental", "id": ""})
            records = saved["evidence_records"]
            self.assertEqual(len(records), 6)
            self.assertEqual(len({r["record_id"] for r in records}), 6)
            self.assertIn("12 months", records[0]["follow_up"])
            self.assertTrue(records[1]["follow_up"].startswith("3 months"))
            self.assertIn("post hoc", records[2]["stage_track"].lower())
            self.assertIn("-0.64", records[2]["value"])
            self.assertIn("1.905 mm", records[3]["value"])
            self.assertIn("8 ASC+PRP and 6 EMD", records[3]["sample_size"])
            self.assertIn("no significant", records[4]["value"])
            self.assertIn("equivalence margin", records[4]["notes"])
            self.assertIn("16 consented", records[5]["value"])
            self.assertEqual(records[5]["status"], "source reports mixed signal")
            self.assertTrue(all(not r["dataset_sha256"] for r in records))
            saved = instance.campaign({**saved, "title": "Edited research question"})
            self.assertEqual([r["record_id"] for r in saved["evidence_records"]], [r["record_id"] for r in records])

    def test_gingival_starter_keeps_clinical_histology_and_durability_endpoints_separate(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        authored = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/gingival_endpoint_review.json").read_text(encoding="utf-8"))
        source_seeds = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/desk_seeds.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "gingival-barrier-gap")
        source_starter = next(s for s in source_seeds["campaign_starters"]["dental"] if s["id"] == "gingival-barrier-gap")
        records = authored["evidence_records"]
        self.assertEqual(len(records), 5)
        self.assertEqual(starter["evidence_records"], records)
        self.assertEqual(source_starter["evidence_records"], records)
        self.assertEqual({record["species"] for record in records}, {"Human", "Canine", "Rabbit"})
        self.assertIn("16 test and 14 control sites", records[0]["sample_size"])
        self.assertIn("10 men", records[1]["sample_size"])
        self.assertIn("nested", records[2]["independent_unit"])
        self.assertIn("Seven days", records[3]["follow_up"])
        self.assertIn("43 sites", records[4]["sample_size"])
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "dental", "id": ""})
            saved_records = [{key: value for key, value in record.items() if key != "record_id"}
                             for record in saved["evidence_records"]]
            self.assertEqual(saved_records, records)
            self.assertEqual(len({record["record_id"] for record in saved["evidence_records"]}), 5)

    def test_ameloblast_source_audits_are_editable_metadata(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        source_seeds = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/desk_seeds.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["organoids"] if s["id"] == "ameloblast-rna-contrast")
        source_starter = next(s for s in source_seeds["campaign_starters"]["organoids"] if s["id"] == starter["id"])
        self.assertEqual(starter["evidence_records"], source_starter["evidence_records"])
        self.assertEqual(len(starter["evidence_records"]), 4)
        provenance = starter["evidence_records"][2]
        self.assertEqual(provenance["source_title"], "GSE307437: sample-to-archive provenance links")
        self.assertIn("6 GEO samples", provenance["value"])
        self.assertIn("6 BioSample links", provenance["value"])
        self.assertIn("6 SRA experiment links", provenance["value"])
        self.assertIn("KO-10 and KO-13", provenance["notes"])
        self.assertFalse(provenance["dataset_sha256"])
        record = starter["evidence_records"][3]
        self.assertEqual(record["axis_id"], "control")
        self.assertIn("7 sheets", record["value"])
        self.assertIn("178 nonempty cells", record["value"])
        self.assertIn("0 formulas", record["value"])
        self.assertIn("not itemized per mouse", record["independent_unit"])
        self.assertIn("2 biological replicates per condition", record["sample_size"])
        self.assertFalse(record["dataset_sha256"])
        self.assertIn("no sample or graft-outcome identifiers", starter["structure_notes"])
        self.assertIn("linked BioSample and SRA experiment records", starter["structure_notes"])
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "organoids", "id": ""})
            saved_records = [{key: value for key, value in item.items() if key != "record_id"}
                             for item in saved["evidence_records"]]
            self.assertEqual(saved_records, starter["evidence_records"])
            self.assertEqual(len({item["record_id"] for item in saved["evidence_records"]}), 4)

    def test_missing_manifest_dependency_returns_an_invalid_card_without_thread_exit(self):
        validator = desk.experiment_manifest_tools()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = desk.Desk(root / "state")
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            folder = root / "studies" / "constructed-fixture"
            folder.mkdir(parents=True)
            (folder / "experiment.json").write_text("{}", encoding="utf-8")
            with patch.object(desk, "HOME", root), patch.object(desk, "experiment_manifest_tools", return_value=validator), patch.object(validator, "jsonschema", None):
                result = instance.experiments()
            self.assertEqual(len(result["experiments"]), 1)
            self.assertEqual(result["experiments"][0]["validation_status"], "invalid")
            self.assertIn("jsonschema is required", result["experiments"][0]["validation_error"])


if __name__ == "__main__":
    unittest.main()
