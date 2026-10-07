#!/usr/bin/env python3
"""regen — local stand-in for ChatGPT / Antigravity science-plugin lookups.

Subcommands talk to public APIs or local binaries. Fetches and runs write
provenance under $REGEN_DATA/provenance/; hosted folds also save run manifests.

Examples:
  regen pubmed "AK2 splice variant iPSC" --retmax 15
  regen openalex "Yamanaka reprogramming factors" --limit 5
  regen europepmc "organoid oxygen diffusion" --limit 5
  regen uniprot P00520
  regen interpro P04637
  regen ensembl ENSG00000141510
  regen afdb P04637
  regen pdb 1A3N
  regen msa data/seqs.fasta -o data/seqs.aln
  regen fold-route P04637
  regen fold-japanfold submit --fasta examples/ubiquitin-1ubq.fasta --out data/structures/openfold3/ubiquitin-run
  regen fold-nvidia predict examples/openfold3-nvidia-1ubq.json --out data/structures/openfold3/nvidia-run
  regen compare-structures data/structures/reference.cif data/structures/prediction.cif
  regen rdkit "CCO" --descriptors
  regen dock-vina receptor.pdbqt ligand.pdbqt --center_x 10 --center_y 12 --center_z 8 --size_x 20 --size_y 20 --size_z 20 -o data/structures/run.pdbqt
  regen dock-gnina receptor.pdbqt ligand.pdbqt --center_x 10 --center_y 12 --center_z 8 --size_x 20 --size_y 20 --size_z 20 -o data/structures/run.sdf
  regen docking-benchmark data/structures/controls.csv --direction lower --out data/structures/validation-01
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(os.environ.get("REGEN_ROOT", str(Path(__file__).resolve().parents[1])))
DATA = Path(os.environ.get("REGEN_DATA", ROOT / "data"))
CACHE = Path(os.environ.get("REGEN_CACHE", ROOT / "cache"))
PROV = DATA / "provenance"
EMAIL = os.environ.get("EMAIL") or os.environ.get("OPENALEX_MAILTO") or "regen-workbench@local"
NCBI_KEY = os.environ.get("NCBI_API_KEY", "")
OPENALEX_KEY = os.environ.get("OPENALEX_API_KEY", "")

UA = f"regen-workbench/0.1 (mailto:{EMAIL})"

# HTTP error codes that warrant an automatic retry.
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0

GNINA_VERSION = "1.3.3"
GNINA_ASSET_URL = "https://github.com/gnina/gnina/releases/download/v1.3.3/gnina.cuda12.8.static"
GNINA_ASSET_SIZE = 2_056_131_000
GNINA_ASSET_SHA256 = "3340c1f49cd3c7c84d8699182a1c6af13c7fa2a22448d1204640446106f72172"


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def ensure_dirs() -> None:
    for p in (
        DATA, CACHE, PROV, DATA / "structures", DATA / "sequences", DATA / "literature",
    ):
        p.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_executable(path: str | Path | None, expected_sha256: str | None = None) -> dict[str, Any]:
    if not path:
        return {"available": False, "path": None, "version": None, "sha256": None, "error": "not installed"}
    executable = Path(path)
    if not executable.is_file():
        return {"available": False, "path": str(executable), "version": None, "sha256": None, "error": "not a regular file"}
    digest = sha256_file(executable)
    if expected_sha256 and digest != expected_sha256:
        return {"available": False, "path": str(executable), "version": None, "sha256": digest, "error": "binary SHA-256 does not match pinned release"}
    try:
        completed = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "path": str(executable), "version": None, "sha256": digest, "error": f"runtime probe failed: {exc.__class__.__name__}"}
    version = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0 or not version:
        return {"available": False, "path": str(executable), "version": version.splitlines()[0][:200] if version else None,
                "sha256": digest, "error": f"runtime probe failed with status {completed.returncode}"}
    return {"available": True, "path": str(executable), "version": version.splitlines()[0][:200], "sha256": digest, "error": None}


def record(action: str, payload: dict[str, Any], outputs: list[Path] | None = None) -> Path:
    ensure_dirs()
    rec = {
        "action": action,
        "when": now(),
        "payload": payload,
        "outputs": [],
    }
    for p in outputs or []:
        if p.exists() and p.is_file():
            rec["outputs"].append({"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size})
        else:
            rec["outputs"].append({"path": str(p), "missing": True})
    # Nanosecond time avoids same-action receipts overwriting each other when
    # two MCP clients/tools run concurrently within one wall-clock second.
    dest = PROV / f"{time.time_ns()}_{action.replace(' ', '_')}.json"
    dest.write_text(json.dumps(rec, indent=2))
    print(f"# provenance {dest}")
    return dest


def _http_with_retry(req: Request, timeout: int) -> Any:
    """Execute an HTTP request with retry/backoff on transient errors.

    Retries up to _MAX_RETRIES times on server errors (500/502/503/504),
    rate limits (429), and connection-level failures.  Backoff doubles
    each attempt (1 s, 2 s, 4 s …).  Client errors like 404 are raised
    immediately.
    """
    from urllib.error import HTTPError, URLError

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return urlopen(req, timeout=timeout)
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP_CODES:
                raise
            last_exc = exc
        except (URLError, OSError) as exc:
            last_exc = exc
        if attempt < _MAX_RETRIES:
            delay = _BACKOFF_BASE_SECONDS * (2 ** attempt)
            print(
                f"# retry {attempt + 1}/{_MAX_RETRIES} after "
                f"{type(last_exc).__name__}, waiting {delay:.0f}s",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def http_json(url: str, timeout: int = 60, headers: dict[str, str] | None = None) -> Any:
    request_headers = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    req = Request(url, headers=request_headers)
    with _http_with_retry(req, timeout) as r:
        return json.loads(r.read().decode())


def http_text(url: str, timeout: int = 60) -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with _http_with_retry(req, timeout) as r:
        return r.read().decode()


def http_bytes(url: str, timeout: int = 120) -> bytes:
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with _http_with_retry(req, timeout) as r:
        return r.read()


def write_bytes(path: Path, blob: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return path


def snapshot_path(directory: Path, prefix: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", prefix).strip("._-") or "snapshot"
    candidate = directory / f"{safe_prefix}_{time.time_ns()}{suffix}"
    while candidate.exists():
        candidate = directory / f"{safe_prefix}_{time.time_ns()}{suffix}"
    return candidate


# ---------- commands ----------

def cmd_pubmed(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen pubmed")
    p.add_argument("query")
    p.add_argument("--retmax", type=int, default=10)
    p.add_argument("--out", default=None)
    ns = p.parse_args(args)
    params = {
        "db": "pubmed",
        "term": ns.query,
        "retmax": str(ns.retmax),
        "retmode": "json",
        "tool": "regen-workbench",
        "email": EMAIL,
    }
    if NCBI_KEY:
        params["api_key"] = NCBI_KEY
    search = http_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode(params))
    ids = search.get("esearchresult", {}).get("idlist", [])
    summaries = []
    if ids:
        sparams = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
            "tool": "regen-workbench",
            "email": EMAIL,
        }
        if NCBI_KEY:
            sparams["api_key"] = NCBI_KEY
        sumj = http_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urlencode(sparams))
        result = sumj.get("result", {})
        for pmid in ids:
            rec = result.get(pmid, {})
            summaries.append(
                {
                    "pmid": pmid,
                    "title": rec.get("title"),
                    "source": rec.get("source"),
                    "pubdate": rec.get("pubdate"),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
            )
    dest = Path(ns.out) if ns.out else DATA / "literature" / f"pubmed_{time.time_ns()}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"query": ns.query, "hits": summaries}, indent=2))
    for h in summaries:
        print(f"{h['pmid']}\t{h.get('pubdate','')}\t{h.get('title','')}")
    record("pubmed", {"query": ns.query, "n": len(summaries)}, [dest])


def cmd_uniprot(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen uniprot")
    p.add_argument("accession")
    ns = p.parse_args(args)
    acc = ns.accession.strip()
    meta = http_json(f"https://rest.uniprot.org/uniprotkb/{acc}.json")
    fasta = http_text(f"https://rest.uniprot.org/uniprotkb/{acc}.fasta")
    stamp = time.time_ns()
    safe_acc = re.sub(r"[^A-Za-z0-9._-]+", "_", acc).strip("._-") or "accession"
    meta_path = DATA / "sequences" / f"{safe_acc}_{stamp}.uniprot.json"
    fa_path = DATA / "sequences" / f"{safe_acc}_{stamp}.fasta"
    meta_path.write_text(json.dumps(meta, indent=2))
    fa_path.write_text(fasta)
    rec = meta.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", acc)
    org = meta.get("organism", {}).get("scientificName", "")
    length = meta.get("sequence", {}).get("length")
    print(f"{acc}\t{org}\t{length}aa\t{rec}")
    record("uniprot", {"accession": acc}, [meta_path, fa_path])


def cmd_afdb(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen afdb")
    p.add_argument("uniprot")
    ns = p.parse_args(args)
    acc = ns.uniprot.strip()
    meta = http_json(f"https://alphafold.ebi.ac.uk/api/prediction/{acc}")
    if not meta:
        die(f"no AFDB entry for {acc}")
    entry = meta[0] if isinstance(meta, list) else meta
    structure_url = entry.get("cifUrl") or entry.get("pdbUrl")
    if not structure_url:
        die("AFDB entry missing structure URL")
    extension = ".cif" if entry.get("cifUrl") else ".pdb"
    blob = http_bytes(structure_url)
    dest = snapshot_path(DATA / "structures", f"AF-{acc}", extension)
    write_bytes(dest, blob)
    summary = {
        "uniprot": acc,
        "entryId": entry.get("entryId"),
        "gene": entry.get("gene"),
        "uniprotDescription": entry.get("uniprotDescription"),
        "globalMetricValue": entry.get("globalMetricValue"),
        "structure": str(dest),
        "format": extension.lstrip("."),
    }
    summary["cif" if extension == ".cif" else "pdb"] = str(dest)
    print(json.dumps(summary, indent=2))
    record("afdb", {**summary, "source_url": structure_url}, [dest])


def cmd_pdb(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen pdb")
    p.add_argument("pdb_id")
    ns = p.parse_args(args)
    pdb_id = ns.pdb_id.strip().lower()
    if not re.fullmatch(r"[a-z0-9]{4}", pdb_id):
        die("PDB ID must be four letters or digits")
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    dest = snapshot_path(DATA / "structures", f"pdb-{pdb_id}", ".cif")
    write_bytes(dest, http_bytes(url))
    print(dest)
    record("pdb", {"pdb_id": pdb_id}, [dest])


def cmd_string(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen string")
    p.add_argument("protein")
    p.add_argument("--species", default="9606")
    ns = p.parse_args(args)
    url = (
        "https://string-db.org/api/json/network"
        f"?identifiers={quote(ns.protein)}&species={ns.species}"
    )
    data = http_json(url)
    out = snapshot_path(DATA / "sequences", f"string_{ns.protein}_{ns.species}", ".json")
    out.write_text(json.dumps(data, indent=2))
    print(f"{len(data)} edges -> {out}")
    record("string", {"protein": ns.protein, "species": ns.species}, [out])


def cmd_chembl(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen chembl")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    ns = p.parse_args(args)
    url = (
        "https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?"
        + urlencode({"q": ns.query, "limit": ns.limit})
    )
    data = http_json(url)
    out = DATA / "literature" / f"chembl_{time.time_ns()}.json"
    out.write_text(json.dumps(data, indent=2))
    molecules = data.get("molecules") or data.get("page_meta") and data.get("molecules", [])
    if isinstance(data, dict):
        mols = data.get("molecules", [])
    else:
        mols = data
    for m in mols[: ns.limit]:
        print(f"{m.get('molecule_chembl_id')}\t{m.get('pref_name')}\t{m.get('molecule_type')}")
    record("chembl", {"query": ns.query}, [out])


def cmd_pubchem(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen pubchem")
    p.add_argument("name")
    ns = p.parse_args(args)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(ns.name)}/property/CanonicalSMILES,MolecularWeight,IUPACName/JSON"
    data = http_json(url)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ns.name).strip("._-") or "compound"
    out = DATA / "literature" / f"pubchem_{safe_name}_{time.time_ns()}.json"
    out.write_text(json.dumps(data, indent=2))
    print(json.dumps(data.get("PropertyTable", {}), indent=2)[:2000])
    record("pubchem", {"name": ns.name}, [out])


def cmd_msa(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen msa")
    p.add_argument("fasta")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--engine", default="mafft", choices=["mafft", "muscle", "clustalo"])
    ns = p.parse_args(args)
    src, dest = Path(ns.fasta), Path(ns.out)
    if not src.exists():
        die(f"missing fasta {src}")
    if not src.is_file():
        die(f"fasta input must be a regular file: {src}")
    if dest.exists():
        die(f"refusing to overwrite existing alignment output: {dest}; choose a new path")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ns.engine == "mafft":
        cmd = ["mafft", "--auto", "--quiet", str(src)]
        dest.write_text(subprocess.check_output(cmd, text=True))
    elif ns.engine == "muscle":
        subprocess.check_call(["muscle", "-align", str(src), "-output", str(dest)])
    else:
        subprocess.check_call(["clustalo", "-i", str(src), "-o", str(dest), "--force"])
    print(dest)
    record("msa", {"engine": ns.engine, "input": str(src.resolve()), "input_sha256": sha256_file(src)}, [dest])


def cmd_rdkit(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen rdkit")
    p.add_argument("smiles")
    p.add_argument("--descriptors", action="store_true")
    ns = p.parse_args(args)
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Crippen, Lipinski

    mol = Chem.MolFromSmiles(ns.smiles)
    if mol is None:
        die("invalid SMILES")
    info = {
        "smiles": ns.smiles,
        "atoms": mol.GetNumAtoms(),
        "inchi_key": Chem.MolToInchiKey(mol),
    }
    if ns.descriptors:
        info.update(
            {
                "mw": Descriptors.MolWt(mol),
                "logp": Crippen.MolLogP(mol),
                "tpsa": Descriptors.TPSA(mol),
                "hbd": Lipinski.NumHDonors(mol),
                "hba": Lipinski.NumHAcceptors(mol),
                "rotatable": Lipinski.NumRotatableBonds(mol),
            }
        )
    print(json.dumps(info, indent=2))
    out = DATA / "literature" / f"rdkit_{time.time_ns()}.json"
    out.write_text(json.dumps(info, indent=2))
    record("rdkit", info, [out])


def cmd_pymol_png(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen pymol-png")
    p.add_argument("structure")
    p.add_argument("-o", "--out", required=True)
    ns = p.parse_args(args)
    src, dest = Path(ns.structure), Path(ns.out)
    if not src.is_file():
        die(f"structure input must be a regular file: {src}")
    if dest.exists():
        die(f"refusing to overwrite existing image output: {dest}; choose a new path")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Use Python string literals for user-controlled filesystem paths. Raw
    # interpolation can turn quotes in a filename into executable code.
    source_literal = repr(str(src))
    destination_literal = repr(str(dest))
    script = f"""
from pymol import cmd
cmd.load({source_literal})
cmd.hide("everything")
cmd.show("cartoon")
cmd.color("slate")
cmd.spectrum("b", "blue_white_red")
cmd.bg_color("white")
cmd.png({destination_literal}, dpi=150, ray=0)
cmd.quit()
"""
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".py", prefix="pymol_render_",
        dir=CACHE, delete=False
    ) as handle:
        handle.write(script)
        tmp = Path(handle.name)
    try:
        subprocess.check_call(["pymol", "-cq", str(tmp)])
    finally:
        tmp.unlink(missing_ok=True)
    print(dest)
    record("pymol-png", {"structure": str(src.resolve()), "input_sha256": sha256_file(src)}, [dest])


def cmd_openalex(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen openalex")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    ns = p.parse_args(args)
    params = {"search": ns.query, "per-page": str(ns.limit), "mailto": EMAIL}
    headers = {"Authorization": f"Bearer {OPENALEX_KEY}"} if OPENALEX_KEY else None
    data = http_json("https://api.openalex.org/works?" + urlencode(params), headers=headers)
    results = data.get("results", [])[: ns.limit]
    out = DATA / "literature" / f"openalex_{time.time_ns()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    for r in results:
        print(f"{r.get('publication_year')}\t{r.get('cited_by_count')}\t{r.get('display_name')}")
    record("openalex", {"query": ns.query, "n": len(results)}, [out])


def cmd_europepmc(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen europepmc")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    ns = p.parse_args(args)
    params = {"query": ns.query, "format": "json", "pageSize": str(ns.limit)}
    data = http_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode(params))
    results = data.get("resultList", {}).get("result", [])[: ns.limit]
    out = DATA / "literature" / f"europepmc_{time.time_ns()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    for r in results:
        print(f"{r.get('pmid') or r.get('id')}\t{r.get('pubYear') or r.get('firstPublicationDate')}\t{r.get('title')}")
    record("europepmc", {"query": ns.query, "n": len(results)}, [out])


def cmd_interpro(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen interpro")
    p.add_argument("accession")
    ns = p.parse_args(args)
    acc = ns.accession.strip()
    # InterPro pages results; collect every page or fail rather than save an
    # apparently complete first page. Bound requests for a single tool call.
    endpoint = "https://www.ebi.ac.uk/interpro/api/entry/all/protein/uniprot/"
    url = f"{endpoint}{quote(acc)}?pageSize=50"
    entries: list[dict[str, Any]] = []
    data: dict[str, Any] = {}
    pages = 0
    while url:
        if pages >= 20:
            die(f"InterPro result exceeds 20 pages for {acc}; no partial result saved")
        page = http_json(url)
        if not isinstance(page, dict) or not isinstance(page.get("results"), list):
            die("unexpected InterPro response format")
        if not pages:
            data = page.copy()
        entries.extend(page["results"])
        pages += 1
        next_page = page.get("next")
        if next_page:
            if not isinstance(next_page, str):
                die("unexpected InterPro pagination URL")
            url = urljoin(url, next_page)
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.netloc != "www.ebi.ac.uk" or not parsed.path.startswith(endpoint.removeprefix("https://www.ebi.ac.uk")):
                die("unexpected InterPro pagination URL")
        else:
            url = ""
    data["results"] = entries
    data["next"] = None
    data["pages_fetched"] = pages
    out = snapshot_path(DATA / "sequences", f"interpro_{acc}", ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    if not entries:
        print(f"no InterPro entries for {acc}")
    for e in entries:
        meta = e.get("metadata", {})
        print(
            f"{meta.get('accession')}\t{meta.get('type')}\t"
            f"{meta.get('integrated') or '-'}\t{meta.get('name')}"
        )
    record("interpro", {"accession": acc, "n": len(entries), "pages": pages}, [out])


def cmd_ensembl(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen ensembl")
    p.add_argument("id")
    ns = p.parse_args(args)
    record_id = ns.id.strip()
    data = http_json(
        f"https://rest.ensembl.org/lookup/id/{quote(record_id)}"
        "?content-type=application/json"
    )
    if not data or "id" not in data:
        die(f"no Ensembl record for {record_id}")
    out = snapshot_path(DATA / "sequences", f"ensembl_{record_id}", ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    location = ""
    if data.get("seq_region_name"):
        location = f"{data.get('seq_region_name')}:{data.get('start')}-{data.get('end')}"
    print(
        f"{data.get('id')}\t{data.get('biotype')}\t"
        f"{data.get('display_name') or data.get('description')}"
        + (f"\t{location}" if location else "")
    )
    record("ensembl", {"id": record_id}, [out])


def cmd_fold_route(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen fold-route")
    p.add_argument("query", help="UniProt accession or path to FASTA")
    ns = p.parse_args(args)
    q = ns.query
    advice = {
        "query": q,
        "vram_gb": 16,
        "decision_tree": [
            "If query is a UniProt accession, try: regen afdb ACCESSION (free, seconds).",
            "If an experimental structure exists, try: regen pdb PDBID.",
            "If designed / orphan / no good homologs: ESMFold on this laptop for ~<600 aa.",
            "If natural sequence with homologs: colabfold sibling image + public MSA server.",
            "For a modest non-covalent protein-ligand co-folding hypothesis: optional OpenFold3 preview or Boltz; neither is a docking-score substitute.",
            "For a known binding site and prepared small-molecule PDBQT inputs: regen dock-vina; compare poses/scores with independent methods.",
            "If it OOMs or is a large multimer: Tamarind academic job or Colab paid GPU — do not fight the card.",
        ],
        "local_commands": {
            "afdb": f"regen afdb {q}",
            "colabfold": (
                "docker compose --profile gpu run --rm "
                "colabfold /data/sequences/query.fasta /data/structures/colabfold"
            ),
            "esmfold_hint": "python -c 'import esm; print(\"fair-esm present\")'",
            "openfold3": (
                "docker compose --profile openfold3 run --rm openfold3 predict "
                "--query-json=/data/structures/query.json "
                "--output-dir=/data/structures/openfold3/run-01"
            ),
        },
        "model_notes": [
            "OpenFold3 is a separate optional Docker profile; current upstream inference is a preview.",
            "OpenFold3 predicts complex structures; Vina searches poses in a specified binding box.",
            "Neither a predicted complex nor a docking score demonstrates binding, efficacy, safety, or rejuvenation.",
        ],
    }
    # If it looks like an accession, probe AFDB.
    if q.isalnum() and q[0].isalpha() and len(q) <= 10:
        try:
            meta = http_json(f"https://alphafold.ebi.ac.uk/api/prediction/{q}")
            advice["afdb_available"] = bool(meta)
        except Exception as e:
            advice["afdb_available"] = False
            advice["afdb_error"] = str(e)
    print(json.dumps(advice, indent=2))
    record("fold-route", advice, [])


def _docking_input_path(value: str, label: str) -> Path:
    raw = Path(value)
    if not raw.is_absolute():
        raw = ROOT / raw
    try:
        path = raw.resolve(strict=True)
    except OSError:
        die(f"{label} does not exist or cannot be resolved")
    roots = [DATA.resolve(strict=False), (ROOT / "projects").resolve(strict=False)]
    if not any(path == root or root in path.parents for root in roots):
        die(f"{label} must be under {DATA} or {ROOT / 'projects'}")
    if not path.is_file() or path.suffix.lower() != ".pdbqt":
        die(f"{label} must be a regular .pdbqt file")
    if path.stat().st_size == 0 or path.stat().st_size > 25 * 1024 * 1024:
        die(f"{label} must be non-empty and no larger than 25 MiB")
    try:
        with path.open(encoding="ascii", errors="ignore") as handle:
            has_atoms = any(line.startswith(("ATOM  ", "HETATM")) for line in handle)
    except OSError:
        die(f"{label} cannot be read")
    if not has_atoms:
        die(f"{label} contains no ATOM or HETATM records")
    return path


def _docking_output_path(value: str, suffix: str = ".pdbqt") -> Path:
    raw = Path(value)
    if not raw.is_absolute():
        raw = ROOT / raw
    if raw.suffix.lower() != suffix or not raw.name:
        die(f"--out must name a {suffix} file")
    try:
        parent = raw.parent.resolve(strict=True)
        data_root = DATA.resolve(strict=False)
    except OSError:
        die("--out parent must already exist")
    if parent != data_root and data_root not in parent.parents:
        die(f"--out must be under {DATA}")
    dest = parent / raw.name
    if dest.exists() or dest.is_symlink():
        die("--out must be a new file; existing results are never overwritten")
    return dest


def _docking_transcript(
    stdout: str | bytes | None,
    stderr: str | bytes | None,
    replacements: tuple[tuple[str, str], ...] = (),
) -> str:
    parts = []
    for value in (stdout, stderr):
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if value and value.strip():
            parts.append(value.strip())
    transcript = "\n".join(parts)
    for source, target in replacements:
        transcript = transcript.replace(source, target)
    return transcript[-12000:]


def _record_docking_failure(
    action: str,
    settings: dict[str, Any],
    message: str,
    *,
    stdout: str | bytes | None = None,
    stderr: str | bytes | None = None,
    replacements: tuple[tuple[str, str], ...] = (),
    started: float,
) -> None:
    settings.update({
        "status": "failed",
        "error": message[:4000],
        "transcript": _docking_transcript(stdout, stderr, replacements),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    })
    record(action, settings)
    die(message)


def install_gnina() -> dict[str, Any]:
    """Fetch the pinned official Linux binary into the shared, ignored cache."""
    ensure_dirs()
    install_dir = CACHE / "gnina"
    install_dir.mkdir(parents=True, exist_ok=True)
    target = install_dir / "gnina"
    if target.exists():
        if (target.is_file() and target.stat().st_size == GNINA_ASSET_SIZE
                and sha256_file(target) == GNINA_ASSET_SHA256):
            result = {
                "version": GNINA_VERSION,
                "status": "verified_existing",
                "path": str(target),
                "sha256": GNINA_ASSET_SHA256,
            }
            record("install-gnina", result, [target])
            print(json.dumps(result, indent=2))
            return result
        die(f"refusing to overwrite an existing, unverified GNINA file at {target}")

    fd, temp_name = tempfile.mkstemp(prefix=".gnina-download-", dir=install_dir)
    temp_path = Path(temp_name)
    digest = hashlib.sha256()
    total = 0
    try:
        request = Request(
            GNINA_ASSET_URL,
            headers={"User-Agent": UA, "Accept": "application/octet-stream"},
        )
        with os.fdopen(fd, "wb") as output, urlopen(request, timeout=120) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) != GNINA_ASSET_SIZE:
                raise ValueError("release asset size did not match the pinned binary")
            while chunk := response.read(4 * 1024 * 1024):
                total += len(chunk)
                if total > GNINA_ASSET_SIZE:
                    raise ValueError("release asset exceeded its pinned size")
                digest.update(chunk)
                output.write(chunk)
        if total != GNINA_ASSET_SIZE or digest.hexdigest() != GNINA_ASSET_SHA256:
            raise ValueError("release asset failed the pinned size or SHA-256 check")
        os.chmod(temp_path, 0o755)
        os.link(temp_path, target)
    except Exception as exc:
        die(f"GNINA download was not installed: {exc.__class__.__name__}: {exc}")
    finally:
        temp_path.unlink(missing_ok=True)

    result = {
        "version": GNINA_VERSION,
        "status": "installed",
        "path": str(target),
        "size_bytes": total,
        "sha256": digest.hexdigest(),
        "release_url": GNINA_ASSET_URL,
    }
    record("install-gnina", result, [target])
    print(json.dumps(result, indent=2))
    return result


def _docking_command_settings(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    exhaustiveness: int,
    num_modes: int,
    cpu: int,
    seed: int,
) -> list[str]:
    if not 1 <= exhaustiveness <= 64:
        die("exhaustiveness must be between 1 and 64")
    if not 1 <= num_modes <= 20:
        die("num_modes must be between 1 and 20")
    if not 1 <= cpu <= 16:
        die("cpu must be between 1 and 16")
    if not 1 <= seed <= 2147483647:
        die("seed must be between 1 and 2147483647")
    settings: list[str] = []
    for axis, value in zip("xyz", center):
        settings.extend([f"--center_{axis}", str(value)])
    for axis, value in zip("xyz", size):
        settings.extend([f"--size_{axis}", str(value)])
    settings.extend([
        "--exhaustiveness", str(exhaustiveness),
        "--num_modes", str(num_modes),
        "--cpu", str(cpu),
        "--seed", str(seed),
    ])
    return settings


def _run_pdbqt_docking(
    *,
    action: str,
    engine: str,
    executable: str,
    receptor_arg: str,
    ligand_arg: str,
    output_arg: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    command_settings: list[str],
    engine_settings: dict[str, Any],
    output_suffix: str = ".pdbqt",
    timeout: int = 900,
    exhaustiveness: int = 8,
    num_modes: int = 9,
    cpu: int = 4,
    seed: int = 42,
) -> dict[str, Any]:
    receptor = _docking_input_path(receptor_arg, "receptor")
    ligand = _docking_input_path(ligand_arg, "ligand")
    dest = _docking_output_path(output_arg, output_suffix)
    if dest in {receptor, ligand}:
        die("--out must not overwrite an input")
    if len(center) != 3 or any(not math.isfinite(v) or abs(v) > 10000 for v in center):
        die("box center coordinates must be finite and within +/-10000 Angstroms")
    if len(size) != 3 or any(not math.isfinite(v) or v < 0.1 or v > 80 for v in size):
        die("box dimensions must be between 0.1 and 80 Angstroms")
    version = "unknown"
    try:
        version_run = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            timeout=15, check=False,
        )
        version_text = (version_run.stdout or version_run.stderr).strip()
        if version_text:
            version = version_text.splitlines()[0][:200]
    except (OSError, subprocess.TimeoutExpired):
        pass

    started = time.monotonic()
    settings = {
        "engine": engine,
        "version": version,
        "status": "running",
        "receptor": str(receptor),
        "ligand": str(ligand),
        "center_angstrom": list(center),
        "box_size_angstrom": list(size),
        "exhaustiveness": exhaustiveness,
        "num_modes": num_modes,
        "cpu": cpu,
        "seed": seed,
        "interpretation": (
            "Docking scores, CNN predictions, and poses are computational hypotheses, "
            "not measured binding affinity, target engagement, efficacy, safety, "
            "or anti-aging benefit."
        ),
    }
    settings.update(engine_settings)
    with tempfile.TemporaryDirectory(prefix=f".regen-{action}-", dir=dest.parent) as temp_dir:
        temp_dir_path = Path(temp_dir)
        staged_receptor = temp_dir_path / "receptor.pdbqt"
        staged_ligand = temp_dir_path / "ligand.pdbqt"
        temp_output = temp_dir_path / f"poses{output_suffix}"
        shutil.copyfile(receptor, staged_receptor)
        shutil.copyfile(ligand, staged_ligand)
        receptor_sha256 = sha256_file(staged_receptor)
        ligand_sha256 = sha256_file(staged_ligand)
        settings["receptor_sha256"] = receptor_sha256
        settings["ligand_sha256"] = ligand_sha256
        command = [
            executable, "--receptor", str(staged_receptor), "--ligand", str(staged_ligand),
            *command_settings, "--out", str(temp_output),
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            _record_docking_failure(
                action,
                settings,
                f"{engine} exceeded the {timeout // 60}-minute run limit; no result was published",
                stdout=exc.stdout,
                stderr=exc.stderr,
                replacements=(
                    (str(staged_receptor), str(receptor)),
                    (str(staged_ligand), str(ligand)),
                    (str(temp_output), str(dest)),
                ),
                started=started,
            )
        except OSError as exc:
            _record_docking_failure(
                action,
                settings,
                f"could not start {engine}: {exc.__class__.__name__}",
                started=started,
            )
        replacements = (
            (str(staged_receptor), str(receptor)),
            (str(staged_ligand), str(ligand)),
            (str(temp_output), str(dest)),
        )
        transcript = _docking_transcript(completed.stdout, completed.stderr, replacements)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "no diagnostic returned").strip()
            _record_docking_failure(
                action,
                settings,
                f"{engine} exited with status {completed.returncode}: {detail[-4000:]}",
                stdout=completed.stdout,
                stderr=completed.stderr,
                replacements=replacements,
                started=started,
            )
        if not temp_output.is_file() or temp_output.stat().st_size == 0:
            _record_docking_failure(
                action,
                settings,
                f"{engine} reported success but produced no pose file",
                stdout=completed.stdout,
                stderr=completed.stderr,
                replacements=replacements,
                started=started,
            )
        try:
            file_descriptor = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            _record_docking_failure(
                action,
                settings,
                "--out was created by another run; existing results are never overwritten",
                stdout=completed.stdout,
                stderr=completed.stderr,
                replacements=replacements,
                started=started,
            )
        os.close(file_descriptor)
        temp_output.replace(dest)

    settings.update({
        "status": "succeeded",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "transcript": transcript,
    })
    record(action, settings, [dest])
    result = {**settings, "output": str(dest), "transcript": transcript[-12000:]}
    print(json.dumps(result, indent=2))
    return result


def run_vina_docking(
    receptor_arg: str,
    ligand_arg: str,
    output_arg: str,
    *,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    exhaustiveness: int = 8,
    num_modes: int = 9,
    cpu: int = 4,
    seed: int = 42,
) -> dict[str, Any]:
    command_settings = _docking_command_settings(
        center, size, exhaustiveness, num_modes, cpu, seed,
    )
    executable = shutil.which("vina")
    if not executable:
        die("AutoDock Vina is not installed; rebuild the workbench image")
    return _run_pdbqt_docking(
        action="dock-vina",
        engine="AutoDock Vina",
        executable=executable,
        receptor_arg=receptor_arg,
        ligand_arg=ligand_arg,
        output_arg=output_arg,
        center=center,
        size=size,
        command_settings=command_settings,
        engine_settings={},
        exhaustiveness=exhaustiveness,
        num_modes=num_modes,
        cpu=cpu,
        seed=seed,
    )


def run_gnina_docking(
    receptor_arg: str,
    ligand_arg: str,
    output_arg: str,
    *,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    exhaustiveness: int = 8,
    num_modes: int = 9,
    cpu: int = 4,
    seed: int = 42,
    cnn_scoring: str = "rescore",
) -> dict[str, Any]:
    if cnn_scoring not in {"none", "rescore"}:
        die("cnn_scoring must be none or rescore in the bounded workbench runner")
    executable = CACHE / "gnina" / "gnina"
    gnina_status = probe_executable(executable, GNINA_ASSET_SHA256)
    if not gnina_status["available"]:
        die(f"GNINA is unavailable: {gnina_status['error']}; install the pinned release and its runtime libraries")
    executable_sha256 = gnina_status["sha256"]
    command_settings = _docking_command_settings(
        center, size, exhaustiveness, num_modes, cpu, seed,
    )
    command_settings.extend(["--cnn_scoring", cnn_scoring, "--no_gpu"])
    return _run_pdbqt_docking(
        action="dock-gnina",
        engine="GNINA",
        executable=str(executable),
        receptor_arg=receptor_arg,
        ligand_arg=ligand_arg,
        output_arg=output_arg,
        center=center,
        size=size,
        command_settings=command_settings,
        engine_settings={
            "cnn_scoring": cnn_scoring,
            "gpu": False,
            "cnn_outputs_are_predictions": True,
            "executable_sha256": executable_sha256,
        },
        output_suffix=".sdf",
        exhaustiveness=exhaustiveness,
        num_modes=num_modes,
        cpu=cpu,
        seed=seed,
    )


def cmd_dock_vina(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen dock-vina")
    p.add_argument("receptor", help="prepared receptor .pdbqt under data/ or projects/")
    p.add_argument("ligand", help="prepared ligand .pdbqt under data/ or projects/")
    for axis in "xyz":
        p.add_argument(f"--center_{axis}", type=float, required=True)
        p.add_argument(f"--size_{axis}", type=float, required=True)
    p.add_argument("-o", "--out", required=True, help="new output .pdbqt under data/")
    p.add_argument("--exhaustiveness", type=int, default=8)
    p.add_argument("--num_modes", type=int, default=9)
    p.add_argument("--cpu", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    ns = p.parse_args(args)
    run_vina_docking(
        ns.receptor, ns.ligand, ns.out,
        center=(ns.center_x, ns.center_y, ns.center_z),
        size=(ns.size_x, ns.size_y, ns.size_z),
        exhaustiveness=ns.exhaustiveness, num_modes=ns.num_modes,
        cpu=ns.cpu, seed=ns.seed,
    )


def cmd_install_gnina(args: list[str]) -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="regen install-gnina")
    parser.parse_args(args)
    install_gnina()


def cmd_dock_gnina(args: list[str]) -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="regen dock-gnina")
    parser.add_argument("receptor", help="prepared receptor .pdbqt under data/ or projects/")
    parser.add_argument("ligand", help="prepared ligand .pdbqt under data/ or projects/")
    for axis in "xyz":
        parser.add_argument(f"--center_{axis}", type=float, required=True)
        parser.add_argument(f"--size_{axis}", type=float, required=True)
    parser.add_argument("-o", "--out", required=True, help="new output .sdf under data/")
    parser.add_argument("--exhaustiveness", type=int, default=8)
    parser.add_argument("--num_modes", type=int, default=9)
    parser.add_argument("--cpu", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cnn_scoring", choices=("none", "rescore"), default="rescore")
    ns = parser.parse_args(args)
    run_gnina_docking(
        ns.receptor, ns.ligand, ns.out,
        center=(ns.center_x, ns.center_y, ns.center_z),
        size=(ns.size_x, ns.size_y, ns.size_z),
        exhaustiveness=ns.exhaustiveness, num_modes=ns.num_modes,
        cpu=ns.cpu, seed=ns.seed, cnn_scoring=ns.cnn_scoring,
    )


def cmd_docking_benchmark(args: list[str]) -> None:
    import argparse

    from docking_benchmark import create_report

    parser = argparse.ArgumentParser(prog="regen docking-benchmark")
    parser.add_argument("input", help="CSV with compound_id, role, score and optional pose/reference SDF columns")
    parser.add_argument("--direction", choices=("lower", "higher"), default="lower", help="which score direction ranks better")
    parser.add_argument("-o", "--out", required=True, help="new report directory under data/")
    ns = parser.parse_args(args)
    try:
        result = create_report(ns.input, ns.out, ns.direction, workbench_root=ROOT, data_root=DATA, record=record)
    except (ValueError, OSError) as exc:
        die(str(exc))
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))


def cmd_doctor(args: list[str]) -> None:
    ensure_dirs()
    bins = [
        "python", "jupyter", "pymol", "obabel", "mafft", "muscle", "clustalo",
        "blastp", "mmseqs", "foldseek", "samtools", "minimap2", "fastqc",
        "seqkit", "nextflow", "vina", "git",
    ]
    missing_binaries = []
    print("== binaries ==")
    for b in bins:
        path = shutil.which(b)
        print(f"{b:12} {path or 'MISSING'}")
        if not path:
            missing_binaries.append(b)
    gnina_path = CACHE / "gnina" / "gnina"
    gnina_status = probe_executable(gnina_path if gnina_path.is_file() else None, GNINA_ASSET_SHA256)
    if not gnina_path.is_file():
        gnina_status["error"] = "not installed (regen install-gnina)"
    vina_status = probe_executable(shutil.which("vina"))
    print(f"{'vina':12} {vina_status['version'] or vina_status['error']}")
    print(f"{'gnina':12} {gnina_status['version'] or gnina_status['error']}")
    print("\n== python ==")
    failed_imports = []
    for mod in ["Bio", "rdkit", "numpy", "pandas", "scanpy", "anndata", "esm"]:
        try:
            __import__(mod if mod != "rdkit" else "rdkit")
            print(f"{mod:12} ok")
        except Exception as e:
            print(f"{mod:12} FAIL ({e.__class__.__name__})")
            failed_imports.append(mod)
    print("\n== gpu ==")
    gpu_visible = False
    try:
        out = subprocess.check_output(["nvidia-smi", "-L"], text=True, stderr=subprocess.STDOUT)
        print(out.strip())
        gpu_visible = bool(out.strip())
    except Exception as e:
        print("nvidia-smi not visible:", e)
    print("\n== container isolation ==")
    print("Docker socket is intentionally not mounted; manage Docker pipelines from the host.")
    required_failures = list(missing_binaries) + list(failed_imports)
    if not vina_status["available"]:
        required_failures.append("vina runtime probe")
    ok = not required_failures
    record("doctor", {
        "ok": ok,
        "required_failures": required_failures,
        "missing_binaries": missing_binaries,
        "failed_imports": failed_imports,
        "gpu_visible": gpu_visible,
        "vina": vina_status,
        "gnina": gnina_status,
    }, [])
    if not ok:
        raise SystemExit(1)


def cmd_help(_: list[str]) -> None:
    print(__doc__)
    print("commands:")
    for name in sorted(COMMANDS):
        print(f"  regen {name}")


def cmd_expression_contrast(argv: list[str]) -> None:
    from regen_compute import expression_contrast
    try:
        expression_contrast(argv, record)
    except (ValueError, OSError) as exc:
        die(str(exc))


def cmd_compound_screen(argv: list[str]) -> None:
    from regen_compute import compound_screen
    try:
        compound_screen(argv, record)
    except (ValueError, OSError) as exc:
        die(str(exc))


def cmd_pipeline(argv: list[str]) -> None:
    from regen_compute import pipeline
    try:
        pipeline(argv, record)
    except (ValueError, OSError) as exc:
        die(str(exc))


def cmd_verify_dossier(argv: list[str]) -> None:
    from verify_dossier import main as verify_main

    status = verify_main(argv)
    if status:
        raise SystemExit(status)


def cmd_fold_japanfold(argv: list[str]) -> None:
    from regen_japanfold import main as japanfold_main

    status = japanfold_main(argv)
    if status:
        raise SystemExit(status)


def cmd_fold_nvidia(argv: list[str]) -> None:
    from regen_nvidia import main as nvidia_main

    nvidia_main(argv)


def cmd_compare_structures(argv: list[str]) -> None:
    from structure_compare import main as compare_main

    status = compare_main(argv)
    if status:
        raise SystemExit(status)


COMMANDS = {
    "pipeline": cmd_pipeline,
    "expression-contrast": cmd_expression_contrast,
    "compound-screen": cmd_compound_screen,
    "pubmed": cmd_pubmed,
    "openalex": cmd_openalex,
    "europepmc": cmd_europepmc,
    "uniprot": cmd_uniprot,
    "interpro": cmd_interpro,
    "ensembl": cmd_ensembl,
    "afdb": cmd_afdb,
    "pdb": cmd_pdb,
    "string": cmd_string,
    "chembl": cmd_chembl,
    "pubchem": cmd_pubchem,
    "msa": cmd_msa,
    "rdkit": cmd_rdkit,
    "pymol-png": cmd_pymol_png,
    "fold-route": cmd_fold_route,
    "fold-japanfold": cmd_fold_japanfold,
    "fold-nvidia": cmd_fold_nvidia,
    "compare-structures": cmd_compare_structures,
    "dock-vina": cmd_dock_vina,
    "install-gnina": cmd_install_gnina,
    "dock-gnina": cmd_dock_gnina,
    "docking-benchmark": cmd_docking_benchmark,
    "verify-dossier": cmd_verify_dossier,
    "doctor": cmd_doctor,
    "help": cmd_help,
}


def main(argv: list[str] | None = None) -> None:
    ensure_dirs()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        cmd_help([])
        return
    cmd = argv[0]
    if cmd not in COMMANDS:
        die(f"unknown command {cmd}. Try: regen help")
    COMMANDS[cmd](argv[1:])


if __name__ == "__main__":
    main()
