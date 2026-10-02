from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import regen_mcp  # noqa: E402


class McpProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_root = regen_mcp.WORKBENCH_ROOT
        regen_mcp.WORKBENCH_ROOT = Path(self.tempdir.name)
        (regen_mcp.WORKBENCH_ROOT / "data").mkdir()
        (regen_mcp.WORKBENCH_ROOT / "projects").mkdir()

    def tearDown(self) -> None:
        regen_mcp.WORKBENCH_ROOT = self.previous_root
        self.tempdir.cleanup()

    def test_initialize_and_list_tools(self) -> None:
        state = {"initialized": False}
        initialized = regen_mcp.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            state,
        )
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(initialized["result"]["capabilities"], {"tools": {}, "resources": {}})
        self.assertFalse(state["initialized"])

        self.assertIsNone(
            regen_mcp.handle_message(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}, state
            )
        )
        listed = regen_mcp.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, state
        )
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertIn("regen_pubmed", names)
        self.assertIn("regen_rdkit", names)
        self.assertIn("regen_dock_vina", names)
        self.assertIn("regen_dock_gnina", names)
        self.assertIn("regen_docking_benchmark", names)
        self.assertNotIn("run_shell", names)
        self.assertGreaterEqual(len(names), 10)

    def test_initialize_negotiates_supported_fallback(self) -> None:
        result = regen_mcp.handle_message(
            {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {"protocolVersion": "1.0.0"},
            },
            {"initialized": False},
        )
        self.assertEqual(result["result"]["protocolVersion"], regen_mcp.PROTOCOL_VERSION)

    def test_unhashable_protocol_version_falls_back_safely(self) -> None:
        result = regen_mcp.handle_message(
            {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {"protocolVersion": ["bad"]},
            },
            {"initialized": False},
        )
        self.assertEqual(result["result"]["protocolVersion"], regen_mcp.PROTOCOL_VERSION)

    def test_new_literature_and_metadata_tools_map_correctly(self) -> None:
        with patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            regen_mcp.call_tool(
                "regen_openalex", {"query": "cellular reprogramming", "limit": 5}
            )
            regen_mcp.call_tool(
                "regen_europepmc", {"query": "senescence biomarker"}
            )
            regen_mcp.call_tool("regen_interpro", {"accession": "P04637"})
            regen_mcp.call_tool(
                "regen_ensembl", {"id": "ENSG00000141510"}
            )
        expected = [
            ("regen_openalex", ["openalex", "cellular reprogramming", "--limit", "5"]),
            ("regen_europepmc", ["europepmc", "senescence biomarker", "--limit", "10"]),
            ("regen_interpro", ["interpro", "P04637"]),
            ("regen_ensembl", ["ensembl", "ENSG00000141510"]),
        ]
        for call, (tool, argv) in zip(run.call_args_list, expected):
            self.assertEqual(call.args, (tool, argv))

    def test_new_tools_reject_bad_shapes(self) -> None:
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments(
                "regen_openalex", {"query": "x", "limit": 99}
            )
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments(
                "regen_europepmc", {"query": "x", "limit": True}
            )
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments(
                "regen_interpro", {"accession": "P04637/metadata"}
            )
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments(
                "regen_ensembl", {"id": "ENSG00000141510?x=1"}
            )

    def test_tools_cannot_be_called_before_initialized(self) -> None:
        result = regen_mcp.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"initialized": False},
        )
        self.assertEqual(result["error"]["code"], -32002)

    def test_invalid_json_rpc_and_unknown_method(self) -> None:
        malformed = regen_mcp.handle_message({"jsonrpc": "1.0", "id": 7}, {})
        self.assertEqual(malformed["error"]["code"], -32600)
        unknown = regen_mcp.handle_message(
            {"jsonrpc": "2.0", "id": 8, "method": "not/a/method"},
            {"initialized": True},
        )
        self.assertEqual(unknown["error"]["code"], -32601)

    def test_invalid_tool_arguments_are_tool_errors(self) -> None:
        with patch.object(regen_mcp, "run_regen") as run:
            response = regen_mcp.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "regen_pubmed",
                        "arguments": {"query": "aging", "retmax": 10000},
                    },
                },
                {"initialized": True},
            )
        self.assertTrue(response["result"]["isError"])
        run.assert_not_called()

    def test_call_uses_allowlisted_argv_not_a_shell(self) -> None:
        with patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            result = regen_mcp.call_tool(
                "regen_pubmed", {"query": "A; touch /tmp/owned", "retmax": 4}
            )
        self.assertEqual(result, "ok")
        run.assert_called_once_with(
            "regen_pubmed", ["pubmed", "A; touch /tmp/owned", "--retmax", "4"]
        )

    def test_pubmed_option_is_a_named_cli_flag(self) -> None:
        with patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            regen_mcp.call_tool("regen_pubmed", {"query": "stem cell", "retmax": 8})
        run.assert_called_once_with(
            "regen_pubmed", ["pubmed", "stem cell", "--retmax", "8"]
        )

    def test_tool_arguments_map_to_fixed_cli_subcommands(self) -> None:
        with patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            regen_mcp.call_tool("regen_string", {"protein": "TP53", "species": "9606"})
            regen_mcp.call_tool("regen_rdkit", {"smiles": "CCO", "descriptors": True})
        self.assertEqual(
            run.call_args_list[0].args,
            ("regen_string", ["string", "TP53", "--species", "9606"]),
        )
        self.assertEqual(
            run.call_args_list[1].args,
            ("regen_rdkit", ["rdkit", "CCO", "--descriptors"]),
        )

    def test_docking_benchmark_maps_only_confined_paths(self) -> None:
        source = regen_mcp.WORKBENCH_ROOT / "data" / "controls.csv"
        source.write_text("compound_id,role,score\na,active_control,-8\ni,inactive_control,-2\n", encoding="utf-8")
        args = {"input": str(source), "output": "data/benchmark-report", "direction": "higher"}
        with patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            self.assertEqual(regen_mcp.call_tool("regen_docking_benchmark", args), "ok")
        self.assertEqual(run.call_args.args, (
            "regen_docking_benchmark",
            ["docking-benchmark", str(source.resolve()), "--direction", "higher",
             "--out", str((regen_mcp.WORKBENCH_ROOT / "data" / "benchmark-report").resolve())],
        ))
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments("regen_docking_benchmark", {**args, "output": "/etc/report"})

    def test_vina_arguments_map_to_bounded_fixed_cli(self) -> None:
        receptor = regen_mcp.WORKBENCH_ROOT / "data" / "receptor.pdbqt"
        ligand = regen_mcp.WORKBENCH_ROOT / "data" / "ligand.pdbqt"
        receptor.write_text("ATOM      1  C   GLY A   1      0.000   0.000   0.000  0.00  0.00    +0.000 C\n")
        ligand.write_text("HETATM    1  C1  UNL     1      0.000   0.000   0.000  0.00  0.00    +0.000 C\n")
        args = {
            "receptor": str(receptor),
            "ligand": str(ligand),
            "output": "data/docked.pdbqt",
            "center_x": 1,
            "center_y": 2.5,
            "center_z": -3,
            "size_x": 20,
            "size_y": 21,
            "size_z": 22,
            "seed": 7,
        }
        with patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            self.assertEqual(regen_mcp.call_tool("regen_dock_vina", args), "ok")
        self.assertEqual(
            run.call_args.args,
            (
                "regen_dock_vina",
                [
                    "dock-vina", str(receptor.resolve()), str(ligand.resolve()),
                    "-o", str((regen_mcp.WORKBENCH_ROOT / "data" / "docked.pdbqt").resolve()),
                    "--center_x", "1.0", "--center_y", "2.5", "--center_z", "-3.0",
                    "--size_x", "20.0", "--size_y", "21.0", "--size_z", "22.0",
                    "--exhaustiveness", "8", "--num_modes", "9", "--cpu", "4", "--seed", "7",
                ],
            ),
        )

    def test_vina_rejects_bad_boxes_paths_and_existing_outputs(self) -> None:
        receptor = regen_mcp.WORKBENCH_ROOT / "data" / "receptor.pdbqt"
        ligand = regen_mcp.WORKBENCH_ROOT / "data" / "ligand.pdbqt"
        receptor.write_text("ATOM  test\n")
        ligand.write_text("HETATM test\n")
        base = {
            "receptor": str(receptor),
            "ligand": str(ligand),
            "output": "data/docked.pdbqt",
            "center_x": 0,
            "center_y": 0,
            "center_z": 0,
            "size_x": 20,
            "size_y": 20,
            "size_z": 20,
        }
        for changes in (
            {"center_x": float("nan")},
            {"size_y": 0},
            {"cpu": 17},
            {"output": "/etc/owned.pdbqt"},
        ):
            with self.subTest(changes=changes), self.assertRaises(regen_mcp.ToolInputError):
                regen_mcp._validate_arguments("regen_dock_vina", {**base, **changes})
        (regen_mcp.WORKBENCH_ROOT / "data" / "docked.pdbqt").write_text("existing")
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments("regen_dock_vina", base)

    def test_gnina_arguments_map_to_bounded_sdf_runner(self) -> None:
        receptor = regen_mcp.WORKBENCH_ROOT / "data" / "gnina-receptor.pdbqt"
        ligand = regen_mcp.WORKBENCH_ROOT / "data" / "gnina-ligand.pdbqt"
        receptor.write_text("ATOM      1  C   GLY A   1      0.000   0.000   0.000\n")
        ligand.write_text("HETATM    1  C1  UNL     1      0.000   0.000   0.000\n")
        args = {
            "receptor": str(receptor),
            "ligand": str(ligand),
            "output": "data/gnina-docked.sdf",
            "center_x": 1,
            "center_y": 2.5,
            "center_z": -3,
            "size_x": 20,
            "size_y": 21,
            "size_z": 22,
            "cnn_scoring": "rescore",
            "seed": 7,
        }
        with patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            self.assertEqual(regen_mcp.call_tool("regen_dock_gnina", args), "ok")
        self.assertEqual(
            run.call_args.args,
            (
                "regen_dock_gnina",
                [
                    "dock-gnina", str(receptor.resolve()), str(ligand.resolve()),
                    "-o", str((regen_mcp.WORKBENCH_ROOT / "data" / "gnina-docked.sdf").resolve()),
                    "--center_x", "1.0", "--center_y", "2.5", "--center_z", "-3.0",
                    "--size_x", "20.0", "--size_y", "21.0", "--size_z", "22.0",
                    "--exhaustiveness", "8", "--num_modes", "9", "--cpu", "4", "--seed", "7",
                    "--cnn_scoring", "rescore",
                ],
            ),
        )

    def test_gnina_rejects_unbounded_modes_and_wrong_output_extension(self) -> None:
        receptor = regen_mcp.WORKBENCH_ROOT / "data" / "gnina-validation-receptor.pdbqt"
        ligand = regen_mcp.WORKBENCH_ROOT / "data" / "gnina-validation-ligand.pdbqt"
        receptor.write_text("ATOM test\n")
        ligand.write_text("HETATM test\n")
        base = {
            "receptor": str(receptor),
            "ligand": str(ligand),
            "output": "data/gnina-validation.sdf",
            "center_x": 0,
            "center_y": 0,
            "center_z": 0,
            "size_x": 20,
            "size_y": 20,
            "size_z": 20,
        }
        for changes in (
            {"cnn_scoring": "all"},
            {"output": "data/gnina-validation.pdbqt"},
            {"cpu": 17},
        ):
            with self.subTest(changes=changes), self.assertRaises(regen_mcp.ToolInputError):
                regen_mcp._validate_arguments("regen_dock_gnina", {**base, **changes})

    def test_unknown_tool_does_not_run_a_command(self) -> None:
        with patch.object(regen_mcp, "run_regen") as run:
            with self.assertRaises(KeyError):
                regen_mcp.call_tool("shell", {"command": "id"})
        run.assert_not_called()

    def test_notification_cannot_trigger_tool_side_effect(self) -> None:
        with patch.object(regen_mcp, "run_regen") as run:
            response = regen_mcp.handle_message(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "regen_doctor", "arguments": {}},
                },
                {"initialized": True},
            )
        self.assertIsNone(response)
        run.assert_not_called()

    def test_argument_shapes_are_strict(self) -> None:
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments("regen_pubmed", {"query": "test", "oops": "x"})
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments("regen_pubmed", {"query": "test", "retmax": True})
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments("regen_pdb", {"pdb_id": "../../etc"})

    def test_paths_are_confined_to_data_or_projects(self) -> None:
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._contained_path(
                "data/no-such-input.fa", must_exist=True
            )
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._contained_path("/etc/passwd", must_exist=True)
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._contained_path("../../etc/passwd", must_exist=True)
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._contained_path(
                "projects/output.png", must_exist=False, writable=True
            )

    def test_msa_and_structure_inputs_have_size_caps(self) -> None:
        fasta = regen_mcp.WORKBENCH_ROOT / "data" / "large.fa"
        with fasta.open("wb") as handle:
            handle.truncate(25 * 1024 * 1024 + 1)
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments(
                "regen_msa", {"fasta": str(fasta), "output": "data/out.fa"}
            )

        structure = regen_mcp.WORKBENCH_ROOT / "data" / "large.cif"
        with structure.open("wb") as handle:
            handle.truncate(100 * 1024 * 1024 + 1)
        with self.assertRaises(regen_mcp.ToolInputError):
            regen_mcp._validate_arguments(
                "regen_pymol_png",
                {"structure": str(structure), "output": "data/out.png"},
            )

    def test_symlink_path_cannot_escape_allowed_roots(self) -> None:
        projects = regen_mcp.WORKBENCH_ROOT / "projects"
        projects.mkdir(parents=True, exist_ok=True)
        link = projects / "mcp-test-escape-link"
        try:
            try:
                link.symlink_to("/etc", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaises(regen_mcp.ToolInputError):
                regen_mcp._contained_path(
                    "projects/mcp-test-escape-link/passwd", must_exist=True
                )
        finally:
            link.unlink(missing_ok=True)

    def test_runner_redacts_api_key_from_output(self) -> None:
        secret = "example-test-key-not-real"
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f"returned {secret}", stderr=""
        )
        with patch.dict(os.environ, {"NCBI_API_KEY": secret}), patch.object(
            regen_mcp.subprocess, "run", return_value=completed
        ):
            output = regen_mcp.run_regen("regen_pubmed", ["pubmed", "test"])
        self.assertNotIn(secret, output)
        self.assertIn("[REDACTED_NCBI_API_KEY]", output)

    def test_runner_redacts_openalex_key_from_output(self) -> None:
        secret = "example-openalex-test-key"
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f"returned {secret}", stderr=""
        )
        with patch.dict(os.environ, {"OPENALEX_API_KEY": secret}), patch.object(
            regen_mcp.subprocess, "run", return_value=completed
        ):
            output = regen_mcp.run_regen("regen_openalex", ["openalex", "test"])
        self.assertNotIn(secret, output)
        self.assertIn("[REDACTED_OPENALEX_API_KEY]", output)

    def test_malformed_json_is_reported_as_parse_error(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "regen_mcp.py")],
            input="{bad json}\n",
            text=True,
            capture_output=True,
            check=True,
            timeout=5,
        )
        response = json.loads(proc.stdout)
        self.assertEqual(response["error"]["code"], -32700)

    def test_stdout_protocol_is_newline_delimited_json_only(self) -> None:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": regen_mcp.PROTOCOL_VERSION},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "regen_mcp.py")],
            input="\n".join(json.dumps(item) for item in messages) + "\n",
            text=True,
            capture_output=True,
            check=True,
            env={**os.environ, "PYTHONPATH": ""},
            timeout=5,
        )
        self.assertEqual(proc.stderr, "")
        responses = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([item["id"] for item in responses], [1, 2])
        self.assertIn("regen_pubmed", {tool["name"] for tool in responses[1]["result"]["tools"]})


class McpResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_root = regen_mcp.WORKBENCH_ROOT
        self.previous_config = regen_mcp.CONFIG_DIR
        self.previous_data = regen_mcp.DATA_DIR
        regen_mcp.WORKBENCH_ROOT = Path(self.tempdir.name)
        regen_mcp.CONFIG_DIR = regen_mcp.WORKBENCH_ROOT / "workbench" / "config"
        regen_mcp.DATA_DIR = regen_mcp.WORKBENCH_ROOT / "data"
        (regen_mcp.WORKBENCH_ROOT / "data").mkdir()
        (regen_mcp.WORKBENCH_ROOT / "projects").mkdir()

    def tearDown(self) -> None:
        regen_mcp.WORKBENCH_ROOT = self.previous_root
        regen_mcp.CONFIG_DIR = self.previous_config
        regen_mcp.DATA_DIR = self.previous_data
        self.tempdir.cleanup()

    def test_initialize_advertises_resources_capability(self) -> None:
        state = {"initialized": False}
        result = regen_mcp.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            },
            state,
        )
        capabilities = result["result"]["capabilities"]
        self.assertIn("resources", capabilities)
        self.assertIn("tools", capabilities)

    def test_list_resources_returns_known_resources(self) -> None:
        resources = regen_mcp._list_resources()
        uris = {r["uri"] for r in resources}
        self.assertIn("regen://config/tools.yaml", uris)
        self.assertIn("regen://data/provenance", uris)
        for r in resources:
            self.assertIn("name", r)
            self.assertIn("description", r)
            self.assertIn("mimeType", r)

    def test_read_tools_yaml_returns_content(self) -> None:
        regen_mcp.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (regen_mcp.CONFIG_DIR / "tools.yaml").write_text("hardware:\n  assumed_ram_gb: 64\n")
        result = regen_mcp._read_resource("regen://config/tools.yaml")
        text = result["contents"][0]["text"]
        self.assertIn("assumed_ram_gb", text)
        self.assertEqual(result["contents"][0]["mimeType"], "text/yaml")

    def test_read_tools_yaml_missing_file(self) -> None:
        # CONFIG_DIR does not exist in temp dir
        result = regen_mcp._read_resource("regen://config/tools.yaml")
        self.assertIn("not found", result["contents"][0]["text"])

    def test_read_provenance_listing(self) -> None:
        provenance = regen_mcp.DATA_DIR / "provenance"
        provenance.mkdir(parents=True, exist_ok=True)
        (provenance / "123_pubmed.json").write_text('{"action":"pubmed"}')
        (provenance / "456_uniprot.json").write_text('{"action":"uniprot"}')
        result = regen_mcp._read_resource("regen://data/provenance")
        listing = json.loads(result["contents"][0]["text"])
        names = {entry["name"] for entry in listing}
        self.assertIn("123_pubmed.json", names)
        self.assertIn("456_uniprot.json", names)

    def test_read_provenance_empty(self) -> None:
        # provenance dir doesn't exist
        result = regen_mcp._read_resource("regen://data/provenance")
        self.assertEqual(result["contents"][0]["text"], "[]")

    def test_read_individual_receipt(self) -> None:
        provenance = regen_mcp.DATA_DIR / "provenance"
        provenance.mkdir(parents=True, exist_ok=True)
        (provenance / "123_test.json").write_text('{"action":"test","when":"now"}')
        result = regen_mcp._read_resource("regen://data/provenance/123_test.json")
        data = json.loads(result["contents"][0]["text"])
        self.assertEqual(data["action"], "test")

    def test_read_receipt_path_traversal_blocked(self) -> None:
        result = regen_mcp._read_resource("regen://data/provenance/../../../etc/passwd.json")
        self.assertIn("invalid", result["contents"][0]["text"])

    def test_read_receipt_backslash_traversal_blocked(self) -> None:
        result = regen_mcp._read_resource("regen://data/provenance/..\\..\\etc\\passwd.json")
        self.assertIn("invalid", result["contents"][0]["text"])

    def test_read_unknown_resource(self) -> None:
        result = regen_mcp._read_resource("regen://nonexistent")
        self.assertIn("unknown resource", result["contents"][0]["text"])

    def test_resources_list_via_handle_message(self) -> None:
        state = {"initialized": True}
        result = regen_mcp.handle_message(
            {"jsonrpc": "2.0", "id": 10, "method": "resources/list"},
            state,
        )
        self.assertIn("resources", result["result"])
        self.assertIsInstance(result["result"]["resources"], list)

    def test_resources_read_via_handle_message(self) -> None:
        regen_mcp.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (regen_mcp.CONFIG_DIR / "tools.yaml").write_text("test: true\n")
        state = {"initialized": True}
        result = regen_mcp.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "resources/read",
                "params": {"uri": "regen://config/tools.yaml"},
            },
            state,
        )
        self.assertIn("test: true", result["result"]["contents"][0]["text"])


if __name__ == "__main__":
    unittest.main()
