from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen_boltz2 as boltz  # noqa: E402

FAKE_KEY = "test-only-boltz-key-not-a-credential"
CIF = "data_boltz2\n#\nloop_\n_atom_site.group_PDB\n_atom_site.id\nATOM 1\n#\n"


def request_fixture(*, affinity: bool = False, affinity_samples: int = 2) -> dict:
    request = {
        "polymers": [{"id": "A", "molecule_type": "protein", "sequence": "ACDX"}],
    }
    if affinity:
        request.update({
            "ligands": [{"id": "B1", "smiles": "CCO", "predict_affinity": True}],
            "sampling_steps_affinity": 10,
            "diffusion_samples_affinity": affinity_samples,
            "affinity_mw_correction": False,
        })
    return request


def response_fixture(*, affinity: bool = False, affinity_samples: int = 2) -> dict:
    response = {
        "structures": [{"format": "mmcif", "structure": CIF}],
        "confidence_scores": [0.81],
        "ptm_scores": [0.79],
        "iptm_scores": [0.72],
        "ligand_iptm_scores": [0.61] if affinity else [],
        "protein_iptm_scores": [0.78],
        "complex_plddt_scores": [0.86],
        "complex_iplddt_scores": [0.69],
        "complex_pde_scores": [0.31],
        "complex_ipde_scores": [0.42],
        "chains_ptm_scores": [{"A": 0.79}],
        "pair_chains_iptm_scores": [{"A": {"A": 0.79}}],
        "affinities": {},
        "metrics": {"inference_seconds": 1.25},
        "pae": None,
        "pde": None,
    }
    if affinity:
        response["affinities"] = {"B1": {
            "affinity_pic50": [5.1, 5.4],
            "affinity_pred_value": [0.2, 0.1],
            "affinity_probability_binary": [0.45, 0.7],
            "model_1_affinity_pred_value": [0.25, 0.12],
            "model_1_affinity_probability_binary": [0.4, 0.65],
            "model_2_affinity_pred_value": [0.15, 0.08],
            "model_2_affinity_probability_binary": [0.5, 0.75],
        }}
        if affinity_samples != 2:
            for values in response["affinities"]["B1"].values():
                values[:] = values[:affinity_samples]
    return response


def raw_fixture(response: dict) -> bytes:
    return json.dumps(response, indent=1, allow_nan=False).encode("utf-8")


class TrackingBody(io.BytesIO):
    def __init__(self, value: bytes) -> None:
        super().__init__(value)
        self.positions_at_close = []

    def close(self) -> None:
        self.positions_at_close.append(super().tell())
        super().close()


class FakeResponse:
    def __init__(self, blob: bytes, status: int = 200) -> None:
        self.blob = blob
        self.status = status
        self.read_limits = []

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self.blob

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class RequestValidationTests(unittest.TestCase):
    def test_protein_defaults_canonical_sorted_and_nonmutating(self) -> None:
        original = request_fixture()
        before = copy.deepcopy(original)
        encoded = boltz.validate_request(original)
        self.assertEqual(original, before)
        self.assertEqual(encoded, json.dumps(
            json.loads(encoded), sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode())
        self.assertEqual(json.loads(encoded), {
            "polymers": [{"id": "A", "molecule_type": "protein", "sequence": "ACDX"}],
            "ligands": [], "recycling_steps": 3, "sampling_steps": 50,
            "diffusion_samples": 1, "step_scale": 1.638, "output_format": "mmcif",
        })

    def test_sequence_and_smiles_boundaries(self) -> None:
        for sequence in ("A", "X", "ACDEFGHIKLMNPQRSTVWYX", "A" * 4096):
            with self.subTest(length=len(sequence)):
                request = request_fixture()
                request["polymers"][0]["sequence"] = sequence
                self.assertEqual(json.loads(boltz.validate_request(request))["polymers"][0]["sequence"], sequence)
        ligand = {"id": "B1", "smiles": "C" * 4096}
        request = request_fixture()
        request["ligands"] = [ligand]
        canonical = json.loads(boltz.validate_request(request))
        self.assertEqual(canonical["ligands"][0]["predict_affinity"], False)
        self.assertEqual(canonical["ligands"][0]["smiles"], "C" * 4096)

    def test_affinity_defaults_and_explicit_lower_settings(self) -> None:
        default_request = request_fixture(affinity=True)
        del default_request["sampling_steps_affinity"]
        del default_request["diffusion_samples_affinity"]
        canonical = json.loads(boltz.validate_request(default_request))
        self.assertEqual(canonical["sampling_steps_affinity"], 200)
        self.assertEqual(canonical["diffusion_samples_affinity"], 5)
        self.assertFalse(canonical["affinity_mw_correction"])
        lower = json.loads(boltz.validate_request(request_fixture(affinity=True)))
        self.assertEqual(lower["sampling_steps_affinity"], 10)
        self.assertEqual(lower["diffusion_samples_affinity"], 2)
        ccd = request_fixture()
        ccd["ligands"] = [{"id": "B1", "ccd": "ATP1", "predict_affinity": False}]
        self.assertEqual(json.loads(boltz.validate_request(ccd))["ligands"][0]["ccd"], "ATP1")

    def test_rejects_polymer_shape_type_and_capabilities(self) -> None:
        bad_polymers = [None, [], [request_fixture()["polymers"][0]] * 2]
        for value in bad_polymers:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    boltz.validate_request({"polymers": value})
        mutations = [
            {"id": "B"}, {"molecule_type": "dna"}, {"molecule_type": "rna"},
            {"msa": "query"}, {"constraints": []}, {"templates": []},
            {"modifications": []}, {"cyclic": True}, {"sequence": ""},
            {"sequence": "AB"}, {"sequence": "A" * 4097}, {"sequence": 4},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                request = request_fixture()
                request["polymers"][0].update(mutation)
                with self.assertRaises(ValueError):
                    boltz.validate_request(request)
        with self.assertRaises(ValueError):
            boltz.validate_request({"polymers": [{"id": "A", "molecule_type": "protein"}]})

    def test_rejects_invalid_ligands(self) -> None:
        ligands = [
            None, {}, [{"id": "B1", "smiles": "CCO"}, {"id": "B1", "ccd": "CCO"}],
            [{"id": "A", "smiles": "CCO"}], [{"smiles": "CCO"}],
            [{"id": "B1"}], [{"id": "B1", "smiles": "CCO", "ccd": "CCO"}],
            [{"id": "B1", "ccd": "atp"}], [{"id": "B1", "ccd": "TOOLONG"}],
            [{"id": "B1", "ccd": 3}], [{"id": "B1", "smiles": ""}],
            [{"id": "B1", "smiles": "CC O"}], [{"id": "B1", "smiles": "C\n"}],
            [{"id": "B1", "smiles": "C" * 4097}], [{"id": "B1", "smiles": 3}],
            [{"id": "B1", "smiles": "CCO", "predict_affinity": 1}],
            [{"id": "B1", "smiles": "CCO", "modifications": []}],
        ]
        for value in ligands:
            with self.subTest(value=value):
                request = request_fixture()
                request["ligands"] = value
                with self.assertRaises(ValueError):
                    boltz.validate_request(request)

    def test_rejects_unknown_top_level_capabilities(self) -> None:
        for name in (
            "msa", "constraints", "templates", "affinity_embeddings", "embeddings",
            "max_parallel_samples", "without_potentials", "concatenate_msas",
            "write_pae", "write_pde", "unknown",
        ):
            with self.subTest(name=name):
                request = request_fixture()
                request[name] = None
                with self.assertRaises(ValueError):
                    boltz.validate_request(request)

    def test_structure_setting_types_ranges_and_nonfinite(self) -> None:
        cases = [
            ("recycling_steps", value) for value in (True, 1.0, 0, 11)
        ] + [
            ("sampling_steps", value) for value in (False, 50.0, 9, 1001)
        ] + [
            ("diffusion_samples", value) for value in (True, 1.0, 0, 2)
        ] + [
            ("step_scale", value) for value in (True, "1.6", 0.49, 5.01, float("nan"), float("inf"))
        ] + [("output_format", value) for value in ("pdb", "cif", None)]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                request = request_fixture()
                request[name] = value
                with self.assertRaises(ValueError):
                    boltz.validate_request(request)
        request = request_fixture()
        request.update({"recycling_steps": 1, "sampling_steps": 10, "step_scale": 0.5})
        self.assertEqual(json.loads(boltz.validate_request(request))["sampling_steps"], 10)

    def test_affinity_settings_require_affinity_and_validate_ranges(self) -> None:
        for name in boltz.AFFINITY_SETTING_FIELDS:
            with self.subTest(unrequested=name):
                request = request_fixture()
                request[name] = False if name == "affinity_mw_correction" else 10
                with self.assertRaises(ValueError):
                    boltz.validate_request(request)
        cases = [
            ("sampling_steps_affinity", value) for value in (True, 10.0, 9, 1001)
        ] + [
            ("diffusion_samples_affinity", value) for value in (False, 1.0, 0, 11)
        ] + [("affinity_mw_correction", value) for value in (0, 1, "false", None)]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                request = request_fixture(affinity=True)
                request[name] = value
                with self.assertRaises(ValueError):
                    boltz.validate_request(request)

    def test_request_cap_is_enforced(self) -> None:
        with patch.object(boltz, "MAX_REQUEST_BYTES", 32), self.assertRaisesRegex(ValueError, "8 MiB"):
            boltz.validate_request(request_fixture())


class ResponseValidationTests(unittest.TestCase):
    def test_official_shape_protein_fixture_retains_flat_arrays(self) -> None:
        result = boltz.validate_response(response_fixture(), request_fixture())
        self.assertEqual(result["structure"], CIF.encode())
        self.assertEqual(result["scores"]["confidence_scores"], [0.81])
        self.assertEqual(result["scores"]["chains_ptm_scores"], [{"A": 0.79}])
        self.assertEqual(result["scores"]["pair_chains_iptm_scores"], [{"A": {"A": 0.79}}])
        self.assertNotIn("ligand_iptm_scores", result["scores"])
        self.assertEqual(result["affinities"], {})
        self.assertEqual(result["metrics"], {"inference_seconds": 1.25})

    def test_official_shape_affinity_fixture_retains_model_1_and_model_2(self) -> None:
        response = response_fixture(affinity=True)
        result = boltz.validate_response(response, request_fixture(affinity=True))
        affinity = result["affinities"]["B1"]
        for name in boltz.AFFINITY_REQUIRED_FIELDS + boltz.AFFINITY_ENSEMBLE_FIELDS:
            self.assertEqual(affinity[name], response["affinities"]["B1"][name])
        self.assertEqual(affinity["model_1_affinity_pred_value"], [0.25, 0.12])
        self.assertEqual(affinity["model_2_affinity_pred_value"], [0.15, 0.08])
        self.assertNotIn("best", result)

    def test_optional_arrays_and_metrics_may_be_missing_null_or_empty(self) -> None:
        response = response_fixture()
        for name in boltz.OPTIONAL_SCORE_FIELDS:
            response[name] = None
        response["pair_chains_iptm_scores"] = []
        response["metrics"] = None
        result = boltz.validate_response(response, request_fixture())
        self.assertNotIn("iptm_scores", result["scores"])
        self.assertNotIn("pair_chains_iptm_scores", result["scores"])
        self.assertEqual(result["metrics"], {})
        affinity_response = response_fixture(affinity=True)
        for name in boltz.AFFINITY_ENSEMBLE_FIELDS:
            del affinity_response["affinities"]["B1"][name]
        result = boltz.validate_response(affinity_response, request_fixture(affinity=True))
        self.assertEqual(set(result["affinities"]["B1"]), set(boltz.AFFINITY_REQUIRED_FIELDS))

    def test_rejects_structure_cardinality_format_url_and_invalid_cif(self) -> None:
        mutations = [
            [], [{}], [response_fixture()["structures"][0], response_fixture()["structures"][0]],
            [{"format": "cif", "structure": CIF}],
            [{"format": "mmcif", "structure": "https://example.test/model.cif"}],
            [{"format": "mmcif", "structure": "data_model\nno atoms\n"}],
            [{"format": "mmcif"}], [None],
        ]
        for structures in mutations:
            with self.subTest(structures=structures):
                response = response_fixture()
                response["structures"] = structures
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture())
        with patch.object(boltz, "MAX_STRUCTURE_BYTES", len(CIF.encode()) - 1):
            with self.assertRaisesRegex(boltz.NvidiaError, "oversized"):
                boltz.validate_response(response_fixture(), request_fixture())

    def test_rejects_missing_malformed_nonfinite_and_cardinality_scores(self) -> None:
        for name in boltz.REQUIRED_SCORE_FIELDS + ("chains_ptm_scores",):
            with self.subTest(missing=name):
                response = response_fixture()
                del response[name]
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture())
        for value in ([0.1, 0.2], [], [True], ["0.8"], [float("nan")], [float("inf")], 0.8):
            with self.subTest(value=value):
                response = response_fixture()
                response["confidence_scores"] = value
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture())

    def test_rejects_invalid_nested_chain_maps(self) -> None:
        values = [
            [{"A": {"A": 0.8}}], [{"A": 0.8}, {"A": 0.8}], [{"": 0.8}],
            [{"A": True}], [{"A": "0.8"}], [[]],
        ]
        for value in values:
            with self.subTest(name="chains", value=value):
                response = response_fixture()
                response["chains_ptm_scores"] = value
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture())
        pair_values = [[{"A": 0.8}], [{"A": {"A": True}}], [{"A": {}}], [{"A": []}]]
        for value in pair_values:
            with self.subTest(name="pairs", value=value):
                response = response_fixture()
                response["pair_chains_iptm_scores"] = value
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture())

    def test_rejects_affinity_key_shape_and_cardinality_errors(self) -> None:
        for unrequested in ({"B1": {}}, None, []):
            with self.subTest(unrequested=unrequested):
                response = response_fixture()
                response["affinities"] = unrequested
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture())
        for affinities in (None, {}, {"C1": {}}, {"B1": {}, "C1": {}}, []):
            with self.subTest(value=affinities):
                response = response_fixture(affinity=True)
                response["affinities"] = affinities
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture(affinity=True))
        for name, value in (
            ("affinity_pic50", [5.1]), ("affinity_pred_value", [True, 0.1]),
            ("affinity_probability_binary", [0.2, float("nan")]),
            ("model_1_affinity_pred_value", [0.2]),
            ("model_2_affinity_probability_binary", "0.2"),
        ):
            with self.subTest(name=name):
                response = response_fixture(affinity=True)
                response["affinities"]["B1"][name] = value
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture(affinity=True))
        response = response_fixture(affinity=True)
        response["affinities"]["B1"]["affinity_embedding"] = [0.1, 0.2]
        with self.assertRaises(boltz.NvidiaError):
            boltz.validate_response(response, request_fixture(affinity=True))

    def test_rejects_non_null_matrices_bad_metrics_and_nonobject(self) -> None:
        for name in ("pae", "pde"):
            response = response_fixture()
            response[name] = [[0.1]]
            with self.subTest(matrix=name), self.assertRaises(boltz.NvidiaError):
                boltz.validate_response(response, request_fixture())
        for value in ([], {"time": "1"}, {"time": True}, {"time": float("inf")}, {"bad key": 1}):
            with self.subTest(metrics=value):
                response = response_fixture()
                response["metrics"] = value
                with self.assertRaises(boltz.NvidiaError):
                    boltz.validate_response(response, request_fixture())
        with self.assertRaises(boltz.NvidiaError):
            boltz.validate_response([], request_fixture())


class PredictTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data = self.root / "data"
        env = patch.dict(os.environ, {"REGEN_DATA": str(self.data)})
        env.start()
        self.addCleanup(env.stop)

    def output(self, name: str) -> Path:
        return self.data / "structures" / "boltz2" / name

    def test_success_preserves_raw_bytes_structure_scores_and_hashes(self) -> None:
        response = response_fixture()
        response["unneeded_url"] = "https://example.test/private-response-link"
        response["unknown_ensemble"] = [0.2]
        raw = raw_fixture(response)
        send = Mock(return_value=(copy.deepcopy(response), raw))
        summary = boltz.predict(request_fixture(), self.output("success"), FAKE_KEY, send=send)
        output = self.output("success")
        self.assertEqual(send.call_count, 1)
        self.assertEqual((output / "request.json").read_bytes(), boltz.validate_request(request_fixture()))
        self.assertEqual((output / "response.json").read_bytes(), raw)
        self.assertEqual((output / "structure-01.mmcif").read_bytes(), CIF.encode())
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(manifest["response"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest["response"]["bytes"], len(raw))
        self.assertEqual(manifest["structures"][0]["sha256"], hashlib.sha256(CIF.encode()).hexdigest())
        self.assertEqual(manifest["structures"][0]["bytes"], len(CIF.encode()))
        self.assertIsNone(manifest["model_version"])
        self.assertEqual(manifest["scores"]["confidence_scores"], [0.81])
        self.assertNotIn("unneeded_url", (output / "manifest.json").read_text())
        self.assertNotIn("best", manifest)
        self.assertEqual(summary["status"], "complete")
        receipt = json.loads(Path(summary["provenance"]).read_text())
        self.assertEqual(receipt["action"], "boltz2-predict")
        self.assertEqual(receipt["payload"]["status"], "complete")
        self.assertEqual(len(receipt["outputs"]), 4)
        for artifact in receipt["outputs"]:
            path = Path(artifact["path"])
            self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(artifact["bytes"], path.stat().st_size)
        self.assertFalse(list(output.parent.glob(".boltz2-staging-*")))

    def test_affinity_manifest_preserves_all_parallel_arrays_without_ranking(self) -> None:
        response = response_fixture(affinity=True)
        raw = raw_fixture(response)
        with patch.object(boltz, "_send", return_value=(response, raw)) as send:
            boltz.predict(request_fixture(affinity=True), self.output("affinity"), FAKE_KEY)
        self.assertEqual(send.call_count, 1)
        manifest = json.loads((self.output("affinity") / "manifest.json").read_text())
        self.assertEqual(manifest["affinities"], response["affinities"])
        self.assertIn("model_1_affinity_pred_value", manifest["affinities"]["B1"])
        self.assertIn("model_2_affinity_pred_value", manifest["affinities"]["B1"])
        self.assertNotIn("best", manifest)
        self.assertIn("not measured IC50, Ki, or Kd", manifest["interpretation"])

    def test_failed_response_publishes_no_success_artifacts(self) -> None:
        response = response_fixture()
        response["confidence_scores"] = [0.8, 0.7]
        send = Mock(return_value=(response, raw_fixture(response)))
        with self.assertRaises(boltz.NvidiaError):
            boltz.predict(request_fixture(), self.output("malformed"), FAKE_KEY, send=send)
        output = self.output("malformed")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(sorted(path.name for path in output.iterdir()), ["request.json", "status.json"])
        status = json.loads((output / "status.json").read_text())
        self.assertEqual(status["status"], "failed")
        self.assertFalse(status["submission_unknown"])
        receipt = json.loads(next((self.data / "provenance").glob("*_boltz2-predict.json")).read_text())
        self.assertEqual(receipt["payload"]["status"], "failed")
        self.assertEqual(len(receipt["outputs"]), 2)

    def test_failure_and_unknown_status_receipts(self) -> None:
        cases = [
            (boltz.NvidiaError("NVIDIA API returned HTTP 401", http_status=401), "failed"),
            (boltz.NvidiaError("NVIDIA API returned HTTP 408", http_status=408, submission_unknown=True), "unknown"),
            (boltz.NvidiaError("NVIDIA API connection failed (TimeoutError); submission status is unknown", submission_unknown=True), "unknown"),
        ]
        for index, (error, expected) in enumerate(cases):
            with self.subTest(expected=expected, index=index):
                send = Mock(side_effect=error)
                with self.assertRaises(boltz.NvidiaError):
                    boltz.predict(request_fixture(), self.output(f"error-{index}"), FAKE_KEY, send=send)
                self.assertEqual(send.call_count, 1)
                status = json.loads((self.output(f"error-{index}") / "status.json").read_text())
                self.assertEqual(status["status"], expected)

    def test_output_key_timeout_and_request_credential_fail_before_transport(self) -> None:
        send = Mock()
        self.output("existing").mkdir(parents=True)
        outside = self.root / "outside"
        symlink = self.root / "linked"
        symlink.symlink_to(self.output("existing"), target_is_directory=True)
        for output in (self.output("existing"), outside, symlink):
            with self.subTest(output=output), self.assertRaises(ValueError):
                boltz.predict(request_fixture(), output, FAKE_KEY, send=send)
        with self.assertRaises(ValueError):
            boltz.predict(request_fixture(), self.output("missing-key"), "", send=send)
        with self.assertRaises(ValueError):
            boltz.predict(request_fixture(), self.output("bad-timeout"), FAKE_KEY, timeout=float("nan"), send=send)
        request = request_fixture()
        request["ligands"] = [{"id": "B1", "smiles": FAKE_KEY}]
        with self.assertRaisesRegex(ValueError, "credential"):
            boltz.predict(request, self.output("request-key"), FAKE_KEY, send=send)
        send.assert_not_called()
        self.assertFalse(outside.exists())
        self.assertFalse(self.output("missing-key").exists())
        self.assertFalse(self.output("bad-timeout").exists())
        self.assertFalse(self.output("request-key").exists())

    def test_response_containing_key_is_not_persisted_or_echoed(self) -> None:
        response = response_fixture()
        response["private"] = FAKE_KEY
        raw = raw_fixture(response)
        with self.assertRaises(boltz.NvidiaError) as caught:
            boltz.predict(request_fixture(), self.output("key-response"), FAKE_KEY,
                          send=Mock(return_value=(response, raw)))
        self.assertNotIn(FAKE_KEY, str(caught.exception))
        output = self.output("key-response")
        self.assertFalse((output / "response.json").exists())
        for path in output.iterdir():
            self.assertNotIn(FAKE_KEY, path.read_text())
        for path in (self.data / "provenance").glob("*_boltz2-predict.json"):
            self.assertNotIn(FAKE_KEY, path.read_text())

    def test_json_escaped_credential_blocks_response_and_structure_publication(self) -> None:
        escaped_first = ("\\u%04x" % ord(FAKE_KEY[0])).encode() + FAKE_KEY[1:].encode()
        for location in ("value", "key", "structure"):
            with self.subTest(location=location):
                response = response_fixture()
                if location == "value":
                    response["unknown_field"] = FAKE_KEY
                elif location == "key":
                    response[FAKE_KEY] = "unknown value"
                else:
                    response["structures"][0]["structure"] = CIF + "# " + FAKE_KEY + "\n"
                raw = raw_fixture(response).replace(FAKE_KEY.encode(), escaped_first)
                self.assertNotIn(FAKE_KEY.encode(), raw)
                output = self.output(f"escaped-{location}")
                with self.assertRaises(boltz.NvidiaError) as caught:
                    boltz.predict(request_fixture(), output, FAKE_KEY,
                                  send=Mock(return_value=(response, raw)))
                self.assertNotIn(FAKE_KEY, str(caught.exception))
                self.assertEqual(
                    sorted(path.name for path in output.iterdir()),
                    ["request.json", "status.json"],
                )
                self.assertFalse((output / "response.json").exists())
                self.assertFalse((output / "structure-01.mmcif").exists())
                for path in output.iterdir():
                    self.assertNotIn(FAKE_KEY, path.read_text())
        for path in (self.data / "provenance").glob("*_boltz2-predict.json"):
            self.assertNotIn(FAKE_KEY, path.read_text())

    def test_send_error_message_is_redacted(self) -> None:
        error = boltz.NvidiaError(f"provider rejected {FAKE_KEY}")
        with self.assertRaises(boltz.NvidiaError) as caught:
            boltz.predict(request_fixture(), self.output("redacted"), FAKE_KEY, send=Mock(side_effect=error))
        self.assertNotIn(FAKE_KEY, str(caught.exception))
        self.assertNotIn(FAKE_KEY, (self.output("redacted") / "status.json").read_text())


class TransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.encoded = boltz.validate_request(request_fixture())

    def opener_for(self, response):
        opener = patch.object(boltz, "build_opener")
        mocked = opener.start()
        self.addCleanup(opener.stop)
        mocked.return_value.open.return_value = response
        return mocked

    def test_fixed_one_shot_post_headers_and_bounded_read(self) -> None:
        response = FakeResponse(raw_fixture(response_fixture()))
        mocked = self.opener_for(response)
        result, raw = boltz._send(self.encoded, FAKE_KEY, 12)
        self.assertEqual(result["confidence_scores"], [0.81])
        self.assertEqual(raw, response.blob)
        request = mocked.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, boltz.ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.data, self.encoded)
        self.assertEqual(request.get_header("Authorization"), f"Bearer {FAKE_KEY}")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertNotIn(FAKE_KEY, request.get_header("User-agent"))
        self.assertEqual(mocked.return_value.open.call_args.kwargs["timeout"], 12.0)
        self.assertEqual(mocked.return_value.open.call_count, 1)
        self.assertEqual(response.read_limits, [boltz.MAX_RESPONSE_BYTES + 1])

    def test_invalid_json_utf8_nonobject_and_nonfinite_fail_without_retry(self) -> None:
        for blob in (b"{", b"\xff", b"[]", b'{"value":NaN}', b'{"a":1,"a":2}'):
            with self.subTest(blob=blob):
                mocked = self.opener_for(FakeResponse(blob))
                with self.assertRaises(boltz.NvidiaError):
                    boltz._send(self.encoded, FAKE_KEY, 5)
                self.assertEqual(mocked.return_value.open.call_count, 1)

    def test_oversize_and_non_200_response_do_not_publish_or_retry(self) -> None:
        with patch.object(boltz, "MAX_RESPONSE_BYTES", 8):
            mocked = self.opener_for(FakeResponse(b"123456789"))
            with self.assertRaisesRegex(boltz.NvidiaError, "100 MiB"):
                boltz._send(self.encoded, FAKE_KEY, 5)
            self.assertEqual(mocked.return_value.open.call_count, 1)
        response = FakeResponse(b"private body", status=201)
        mocked = self.opener_for(response)
        with self.assertRaises(boltz.NvidiaError) as caught:
            boltz._send(self.encoded, FAKE_KEY, 5)
        self.assertEqual(caught.exception.http_status, 201)
        self.assertEqual(response.read_limits, [])

    def test_http_error_status_only_and_submission_semantics(self) -> None:
        for code in (401, 422, 408, 429, 500, 503):
            with self.subTest(code=code):
                body = TrackingBody(f"private body {FAKE_KEY} https://example.test".encode())
                error = HTTPError(boltz.ENDPOINT, code, "provider error", {}, body)
                with patch.object(boltz, "build_opener") as mocked:
                    mocked.return_value.open.side_effect = error
                    with self.assertRaises(boltz.NvidiaError) as caught:
                        boltz._send(self.encoded, FAKE_KEY, 5)
                self.assertEqual(mocked.return_value.open.call_count, 1)
                self.assertEqual(caught.exception.http_status, code)
                self.assertEqual(caught.exception.submission_unknown, code in (408, 429, 500, 503))
                self.assertEqual(str(caught.exception), f"NVIDIA API returned HTTP {code}")
                self.assertNotIn(FAKE_KEY, str(caught.exception))
                self.assertTrue(body.closed)
                self.assertEqual(body.positions_at_close, [0])

    def test_connection_and_timeout_failures_are_submission_unknown(self) -> None:
        for error in (TimeoutError("private timeout"), URLError("private URL"), OSError("private path")):
            with self.subTest(error=type(error).__name__):
                with patch.object(boltz, "build_opener") as mocked:
                    mocked.return_value.open.side_effect = error
                    with self.assertRaises(boltz.NvidiaError) as caught:
                        boltz._send(self.encoded, FAKE_KEY, 5)
                self.assertTrue(caught.exception.submission_unknown)
                self.assertEqual(mocked.return_value.open.call_count, 1)
                self.assertNotIn("private", str(caught.exception))

    def test_unsafe_key_is_sanitized_and_rejected_before_request_construction(self) -> None:
        for suffix in ("\r\nInjected: yes", "\n", "\r", "\x00", "\x7f", "\x80"):
            unsafe_key = "dummy-key" + suffix
            with self.subTest(suffix=repr(suffix)), \
                    patch.object(boltz, "Request") as request, \
                    patch.object(boltz, "build_opener") as opener:
                with self.assertRaises(boltz.NvidiaError) as caught:
                    boltz._send(self.encoded, unsafe_key, 5)
                self.assertEqual(str(caught.exception), "NVIDIA_API_KEY contains unsafe header characters")
                self.assertNotIn(unsafe_key, str(caught.exception))
                self.assertNotIn("Injected", str(caught.exception))
                request.assert_not_called()
                opener.assert_not_called()

    def test_timeout_and_key_validation_precede_transport(self) -> None:
        for timeout in (True, 0, 3601, float("nan"), float("inf"), "5"):
            with self.subTest(timeout=timeout), patch.object(boltz, "build_opener") as mocked:
                with self.assertRaises(ValueError):
                    boltz._send(self.encoded, FAKE_KEY, timeout)
                mocked.assert_not_called()
        with patch.object(boltz, "build_opener") as mocked, self.assertRaises(ValueError):
            boltz._send(self.encoded, "", 5)
        mocked.assert_not_called()

    def test_redirect_is_refused_without_bearer_forwarding_or_retry(self) -> None:
        received = {"origin": 0, "origin_has_bearer": False, "destination": 0}
        destination = ThreadingHTTPServer(("127.0.0.1", 0), type("Destination", (BaseHTTPRequestHandler,), {
            "do_POST": lambda handler: (received.__setitem__("destination", received["destination"] + 1),
                                         handler.send_response(200), handler.end_headers()),
            "log_message": lambda *_args: None,
        }))

        class OriginHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                received["origin"] += 1
                received["origin_has_bearer"] = self.headers.get("Authorization") == f"Bearer {FAKE_KEY}"
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/capture")
                self.end_headers()

            def log_message(self, *_args):
                pass

        origin = ThreadingHTTPServer(("127.0.0.1", 0), OriginHandler)
        threads = [threading.Thread(target=server.serve_forever, daemon=True)
                   for server in (origin, destination)]
        for thread in threads:
            thread.start()
        try:
            with patch.object(boltz, "ENDPOINT", f"http://127.0.0.1:{origin.server_port}/predict"):
                with self.assertRaises(boltz.NvidiaError) as caught:
                    boltz._send(self.encoded, FAKE_KEY, 5)
            self.assertEqual(caught.exception.http_status, 302)
            self.assertFalse(caught.exception.submission_unknown)
            self.assertEqual(received, {"origin": 1, "origin_has_bearer": True, "destination": 0})
        finally:
            for server in (origin, destination):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=2)


class KeyAndCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data = self.root / "data"
        env = patch.dict(os.environ, {"REGEN_DATA": str(self.data)})
        env.start()
        self.addCleanup(env.stop)
        self.request_file = self.root / "request.json"
        self.request_file.write_bytes(raw_fixture(request_fixture()))

    def test_key_loader_uses_only_process_environment_and_never_reads_files(self) -> None:
        with patch.dict(os.environ, {"NVIDIA_API_KEY": f"  {FAKE_KEY}  "}), \
                patch.object(Path, "read_text", side_effect=AssertionError("file read forbidden")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("file read forbidden")), \
                patch.object(Path, "open", side_effect=AssertionError("file open forbidden")):
            self.assertEqual(boltz.load_api_key(), FAKE_KEY)
        with patch.dict(os.environ, {"NVIDIA_API_KEY": ""}):
            self.assertEqual(boltz.load_api_key(), "")

    def test_cli_predict_calls_send_once_and_prints_sanitized_summary(self) -> None:
        output = self.data / "structures" / "boltz2" / "cli-run"
        response = response_fixture()
        with patch.object(boltz, "load_api_key", return_value=FAKE_KEY), \
                patch.object(boltz, "_send", return_value=(response, raw_fixture(response))) as send, \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            status = boltz.main(["predict", str(self.request_file), "--out", str(output)])
        self.assertEqual(status, 0)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(stderr.getvalue(), "")
        summary = json.loads(stdout.getvalue())
        self.assertEqual(summary["structure"], str(output / "structure-01.mmcif"))
        self.assertNotIn(FAKE_KEY, stdout.getvalue())
        self.assertTrue((output / "response.json").is_file())

    def test_cli_exact_predict_arguments(self) -> None:
        output = self.data / "structures" / "boltz2" / "arguments"
        summary = {"status": "complete", "manifest": "manifest.json"}
        with patch.object(boltz, "load_api_key", return_value=FAKE_KEY), \
                patch.object(boltz, "predict", return_value=summary) as predict, \
                contextlib.redirect_stdout(io.StringIO()):
            status = boltz.main(["predict", str(self.request_file), "--out", str(output), "--timeout", "12.5"])
        self.assertEqual(status, 0)
        predict.assert_called_once_with(request_fixture(), output, FAKE_KEY, timeout=12.5)

    def test_cli_request_type_size_output_and_json_errors_are_nonzero(self) -> None:
        directory_request = self.root / "directory"
        directory_request.mkdir()
        bad_json = self.root / "bad.json"
        bad_json.write_text("{")
        oversized = self.root / "large.json"
        oversized.write_bytes(b"123456789")
        outside = self.root / "outside"
        for request, output in (
            (directory_request, outside), (bad_json, outside),
            (self.root / "missing.json", outside),
        ):
            with self.subTest(request=request), patch.object(boltz, "_send") as send, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(boltz.main(["predict", str(request), "--out", str(output)]), 1)
                send.assert_not_called()
        with patch.object(boltz, "MAX_REQUEST_BYTES", 8), patch.object(boltz, "_send") as send, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boltz.main(["predict", str(oversized), "--out", str(outside)]), 1)
            send.assert_not_called()
        with patch.object(boltz, "load_api_key", return_value=FAKE_KEY), patch.object(boltz, "_send") as send, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boltz.main(["predict", str(self.request_file), "--out", str(outside)]), 1)
            send.assert_not_called()
        self.assertFalse(outside.exists())

    def test_cli_malformed_key_is_sanitized_and_makes_no_request(self) -> None:
        output = self.data / "structures" / "boltz2" / "unsafe-key"
        unsafe_key = "dummy-key\r\nInjected: yes"
        with patch.object(boltz, "load_api_key", return_value=unsafe_key), \
                patch.object(boltz, "Request") as request, \
                patch.object(boltz, "_send") as send, \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            status = boltz.main(["predict", str(self.request_file), "--out", str(output)])
        self.assertEqual(status, 1)
        self.assertNotIn(unsafe_key, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn("Injected", stdout.getvalue() + stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "error: NVIDIA_API_KEY contains unsafe header characters\n")
        request.assert_not_called()
        send.assert_not_called()
        self.assertFalse(output.exists())

    def test_cli_expected_failure_does_not_echo_key(self) -> None:
        output = self.data / "structures" / "boltz2" / "failed"
        error = boltz.NvidiaError(f"failed with {FAKE_KEY}")
        with patch.object(boltz, "load_api_key", return_value=FAKE_KEY), \
                patch.object(boltz, "_send", side_effect=error), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            status = boltz.main(["predict", str(self.request_file), "--out", str(output)])
        self.assertEqual(status, 1)
        self.assertNotIn(FAKE_KEY, stdout.getvalue() + stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
