#!/usr/bin/env python3
"""regen — local stand-in for ChatGPT / Antigravity science-plugin lookups.

Subcommands talk to public APIs or local binaries and always write a
provenance record under $REGEN_DATA/provenance/.

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
  regen rdkit "CCO" --descriptors
"""
from __future__ import annotations

import hashlib
import json
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

ROOT = Path(os.environ.get("REGEN_ROOT", "/lab"))
DATA = Path(os.environ.get("REGEN_DATA", ROOT / "data"))
CACHE = Path(os.environ.get("REGEN_CACHE", ROOT / "cache"))
PROV = DATA / "provenance"
EMAIL = os.environ.get("EMAIL") or os.environ.get("OPENALEX_MAILTO") or "regen-workbench@local"
NCBI_KEY = os.environ.get("NCBI_API_KEY", "")

UA = f"regen-workbench/0.1 (mailto:{EMAIL})"

# HTTP error codes that warrant an automatic retry.
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def ensure_dirs() -> None:
    for p in (DATA, CACHE, PROV, DATA / "structures", DATA / "sequences", DATA / "literature"):
        p.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


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


def http_json(url: str, timeout: int = 60) -> Any:
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
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
    meta_path = DATA / "sequences" / f"{acc}.uniprot.json"
    fa_path = DATA / "sequences" / f"{acc}.fasta"
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
    dest = DATA / "structures" / f"AF-{acc}{extension}"
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
    record("afdb", summary, [dest])


def cmd_pdb(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen pdb")
    p.add_argument("pdb_id")
    ns = p.parse_args(args)
    pdb_id = ns.pdb_id.strip().lower()
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    dest = DATA / "structures" / f"{pdb_id}.cif"
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
    out = DATA / "sequences" / f"string_{ns.protein}_{ns.species}.json"
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
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ns.engine == "mafft":
        cmd = ["mafft", "--auto", "--quiet", str(src)]
        dest.write_text(subprocess.check_output(cmd, text=True))
    elif ns.engine == "muscle":
        subprocess.check_call(["muscle", "-align", str(src), "-output", str(dest)])
    else:
        subprocess.check_call(["clustalo", "-i", str(src), "-o", str(dest), "--force"])
    print(dest)
    record("msa", {"engine": ns.engine, "input": str(src)}, [dest])


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
    record("pymol-png", {"structure": str(src)}, [dest])


def cmd_openalex(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="regen openalex")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    ns = p.parse_args(args)
    params = {"search": ns.query, "per-page": str(ns.limit), "mailto": EMAIL}
    data = http_json("https://api.openalex.org/works?" + urlencode(params))
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
    out = DATA / "sequences" / f"interpro_{acc}.json"
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
    out = DATA / "sequences" / f"ensembl_{record_id}.json"
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
            "If complex + ligand + affinity and length fits 16GB: boltz predict (keep tokens modest).",
            "If it OOMs or is a large multimer: Tamarind academic job or Colab paid GPU — do not fight the card.",
        ],
        "local_commands": {
            "afdb": f"regen afdb {q}",
            "colabfold": (
                "docker compose --profile gpu run --rm "
                "-v $PWD/data:/data -v $PWD/cache/colabfold:/cache "
                "colabfold colabfold_batch /data/sequences/query.fasta /data/structures/colabfold"
            ),
            "esmfold_hint": "python -c 'import esm; print(\"fair-esm present\")'",
        },
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
    record("doctor", {
        "ok": not missing_binaries and not failed_imports,
        "missing_binaries": missing_binaries,
        "failed_imports": failed_imports,
        "gpu_visible": gpu_visible,
    }, [])


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


COMMANDS = {
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
