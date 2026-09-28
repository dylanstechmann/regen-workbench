"""Local research orchestration, source intake and bounded RDKit exploration."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import mimetypes
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

import regen
from regen_compute import compound_screen, manifest, write_json

HOME = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).with_name("desk")
PROVIDERS = {
    "pubmed": ("PubMed", "NCBI_API_KEY", False),
    "europepmc": ("Europe PMC", None, False),
    "openalex": ("OpenAlex", "OPENALEX_API_KEY", False),
    "trials": ("ClinicalTrials.gov", None, False),
    "semantic": ("Semantic Scholar", "SEMANTIC_SCHOLAR_API_KEY", False),
    "core": ("CORE", "CORE_API_KEY", True),
    "brave": ("Brave web / forums", "BRAVE_SEARCH_API_KEY", True),
    "exa": ("Exa web / forums", "EXA_API_KEY", True),
}
KINDS = {"search", "compound", "neighbors", "variants", "compare", "conformers"}
BLUEPRINT_FIELDS = ("title", "area", "query", "question", "who", "what", "where", "when", "why", "how", "falsifier", "desired_changes")


def text_field(data, key, default="", maximum=4000):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{key} must be text of at most {maximum} characters")
    return value.strip()


def bounded_int(value, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"Expected an integer from {low} to {high}")
    return value


def public_url(value):
    if not isinstance(value, str) or len(value) > 3000:
        return ""
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def redact(value):
    encoded = json.dumps(value, ensure_ascii=True, allow_nan=False)
    for name, secret in os.environ.items():
        if name == "EMAIL" or any(word in name for word in ("API_KEY", "TOKEN", "SECRET")):
            if len(secret) >= 5:
                encoded = encoded.replace(json.dumps(secret)[1:-1], "[redacted]")
                encoded = encoded.replace(quote(secret, safe=""), "[redacted]")
    return json.loads(encoded)


class ProviderError(Exception):
    pass


def fetch_json(url, headers=None, body=None):
    """Only internal adapters supply URLs. Never return credential-bearing errors."""
    headers = {"User-Agent": regen.UA, "Accept": "application/json", **(headers or {})}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode()
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers=headers, data=payload), timeout=25) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ProviderError("Provider response exceeded 8 MiB")
            result = redact(json.loads(raw))
            if isinstance(result, dict) and (result.get("error") or result.get("errors")):
                raise ProviderError("Provider returned an error object")
            return result
        except HTTPError as exc:
            code = exc.code
            exc.close()
            if attempt == 0 and code in {429, 500, 502, 503, 504}:
                time.sleep(1)
                continue
            raise ProviderError(f"HTTP {code}; provider did not return usable data") from None
        except (URLError, OSError, TimeoutError):
            if attempt == 0:
                continue
            raise ProviderError("Network timeout or connection failure") from None
        except (ValueError, UnicodeError):
            raise ProviderError("Provider returned invalid JSON") from None


def hit(provider, title, url, date="", **extra):
    return {"provider": provider, "title": title or "Untitled record", "url": public_url(url or ""),
            "date": date or "", "evidence_type": "bibliographic record; design not reviewed", **extra}


def search_provider(provider, query, limit):
    key_name = PROVIDERS[provider][1]
    key = os.environ.get(key_name, "") if key_name else ""
    if PROVIDERS[provider][2] and not key:
        raise ProviderError("API key is not configured")
    if provider == "pubmed":
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        params = {"db": "pubmed", "retmode": "json", "tool": "regen-workbench", "email": regen.EMAIL}
        if key:
            params["api_key"] = key
        search = fetch_json(base + "esearch.fcgi?" + urlencode({**params, "term": query, "retmax": limit}))
        if "error" in search or "esearchresult" not in search:
            raise ProviderError("PubMed rejected the search")
        ids = search["esearchresult"].get("idlist", [])
        summaries = fetch_json(base + "esummary.fcgi?" + urlencode({**params, "id": ",".join(ids)})) if ids else {}
        rows = []
        for pmid in ids:
            item = summaries.get("result", {}).get(pmid, {})
            rows.append(hit(provider, item.get("title"), f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", item.get("pubdate"), pmid=pmid,
                            doi=next((a["value"] for a in item.get("articleids", []) if a.get("idtype") == "doi"), "")))
        return {"search": search, "summaries": summaries}, rows
    if provider == "europepmc":
        raw = fetch_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode({"query": query, "format": "json", "pageSize": limit, "resultType": "core"}))
        rows = [hit(provider, r.get("title"), f"https://europepmc.org/article/{r.get('source', 'MED')}/{r.get('id')}", r.get("firstPublicationDate"),
                    pmid=r.get("pmid", ""), doi=r.get("doi", ""), abstract=r.get("abstractText", ""),
                    publication_types=r.get("pubTypeList", {}).get("pubType", []), is_retracted=r.get("isRetracted", "unknown"))
                for r in raw.get("resultList", {}).get("result", [])]
        return raw, rows
    if provider == "openalex":
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        raw = fetch_json("https://api.openalex.org/works?" + urlencode({"search": query, "per-page": limit, "mailto": regen.EMAIL}), headers)
        rows = [hit(provider, r.get("display_name"), r.get("doi") or r.get("id"), r.get("publication_date"),
                    doi=r.get("doi") or "", publication_types=[r.get("type")], is_retracted=r.get("is_retracted")) for r in raw.get("results", [])]
        return raw, rows
    if provider == "trials":
        raw = fetch_json("https://clinicaltrials.gov/api/v2/studies?" + urlencode({"query.term": query, "pageSize": limit, "format": "json"}))
        rows = []
        for study in raw.get("studies", []):
            p = study.get("protocolSection", {})
            ident, status, design = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
            rows.append(hit(provider, ident.get("briefTitle"), f"https://clinicaltrials.gov/study/{ident.get('nctId')}", status.get("lastUpdatePostDateStruct", {}).get("date"),
                            evidence_type="trial registry; registration is not a result", status=status.get("overallStatus"), phases=design.get("phases", []),
                            enrollment=design.get("enrollmentInfo", {}), has_results=study.get("hasResults", False)))
        return raw, rows
    if provider == "semantic":
        raw = fetch_json("https://api.semanticscholar.org/graph/v1/paper/search?" + urlencode({"query": query, "limit": limit, "fields": "title,url,year,abstract,externalIds,publicationTypes"}), {"x-api-key": key} if key else {})
        return raw, [hit(provider, r.get("title"), r.get("url"), str(r.get("year") or ""), abstract=r.get("abstract") or "",
                         doi=(r.get("externalIds") or {}).get("DOI", ""), pmid=(r.get("externalIds") or {}).get("PubMed", ""),
                         publication_types=r.get("publicationTypes") or []) for r in raw.get("data", [])]
    if provider == "core":
        raw = fetch_json("https://api.core.ac.uk/v3/search/works?" + urlencode({"q": query, "limit": limit}), {"Authorization": f"Bearer {key}"})
        return raw, [hit(provider, r.get("title"), r.get("downloadUrl") or f"https://core.ac.uk/works/{r.get('id')}", str(r.get("yearPublished") or ""),
                         doi=r.get("doi") or "", abstract=r.get("abstract") or "") for r in raw.get("results", [])]
    if provider == "brave":
        raw = fetch_json("https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query, "count": limit}), {"X-Subscription-Token": key})
        return raw, [hit(provider, r.get("title"), r.get("url"), r.get("age", ""), snippet=r.get("description", ""),
                         evidence_type="web lead; claim and source type unreviewed") for r in raw.get("web", {}).get("results", [])]
    raw = fetch_json("https://api.exa.ai/search", {"x-api-key": key}, {"query": query, "numResults": limit, "type": "auto"})
    return raw, [hit(provider, r.get("title"), r.get("url"), r.get("publishedDate", ""), evidence_type="web lead; claim and source type unreviewed") for r in raw.get("results", [])]


def molecule(smiles):
    from rdkit import Chem
    if not isinstance(smiles, str) or not 1 <= len(smiles) <= 2000:
        raise ValueError("SMILES must contain 1-2000 characters")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    if mol.GetNumHeavyAtoms() > 100 or len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError("This workspace computes connected small molecules with at most 100 heavy atoms; large peptides retain database records only")
    return mol


def describe(mol, parent=None):
    from rdkit import Chem, DataStructs
    from rdkit.Chem import Crippen, Descriptors, FilterCatalog, Lipinski, rdFingerprintGenerator
    catalog = FilterCatalog.FilterCatalogParams()
    catalog.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
    alerts = FilterCatalog.FilterCatalog(catalog).GetMatches(mol)
    row = {"smiles": Chem.MolToSmiles(mol, isomericSmiles=True), "mw": round(Descriptors.MolWt(mol), 3),
           "logp": round(Crippen.MolLogP(mol), 3), "tpsa": round(Descriptors.TPSA(mol), 3),
           "hbd": Lipinski.NumHDonors(mol), "hba": Lipinski.NumHAcceptors(mol), "rotatable": Lipinski.NumRotatableBonds(mol),
           "pains": [a.GetDescription() for a in alerts], "unspecified_stereo": sum(str(s.specified) == "Unspecified" for s in Chem.FindPotentialStereo(mol))}
    if parent is not None:
        fp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True)
        row["similarity"] = round(DataStructs.TanimotoSimilarity(fp.GetFingerprint(mol), fp.GetFingerprint(parent)), 4)
    return row


def enumerate_variants(parent):
    """Bounded single substitutions at aromatic C-H sites; RDKit sanitizes products."""
    from rdkit import Chem
    seen = {Chem.MolToSmiles(parent)}
    results = []
    for atom in parent.GetAtoms():
        if atom.GetAtomicNum() != 6 or not atom.GetIsAromatic() or atom.GetTotalNumHs() != 1:
            continue
        for element, label in ((9, "fluoro"), (6, "methyl"), (8, "hydroxy")):
            edit = Chem.RWMol(parent)
            anchor = edit.GetAtomWithIdx(atom.GetIdx())
            anchor.SetNumExplicitHs(0)
            anchor.SetNoImplicit(True)
            added = edit.AddAtom(Chem.Atom(element))
            edit.AddBond(atom.GetIdx(), added, Chem.BondType.SINGLE)
            product = edit.GetMol()
            try:
                Chem.SanitizeMol(product)
                smiles = Chem.MolToSmiles(product, isomericSmiles=True)
                molecule(smiles)
            except (ValueError, RuntimeError):
                continue
            if smiles not in seen:
                seen.add(smiles)
                results.append((product, f"{label} at parent atom {atom.GetIdx()}"))
            if len(results) == 18:
                return results
    return results


class Desk:
    def __init__(self, root=None, recover_pending=False):
        self.root = Path(root) if root else regen.DATA / "research-desk"
        self.runs = self.root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending = 0
        self.store_path = self.root / "workspace.json"
        seeds = json.loads((HOME / "config" / "research-blueprints.json").read_text(encoding="utf-8"))
        self.seed_findings = seeds.get("findings", [])
        self.store = json.loads(self.store_path.read_text(encoding="utf-8")) if self.store_path.exists() else {"blueprints": seeds["blueprints"], "notes": []}
        known = {item["id"] for item in self.store["blueprints"]}
        added = [item for item in seeds["blueprints"] if item["id"] not in known]
        self.store["blueprints"].extend(added)
        priority = seeds.get("focus_order", [item["id"] for item in seeds["blueprints"]])
        rank = {area_id: index for index, area_id in enumerate(priority)}
        ordered = sorted(self.store["blueprints"], key=lambda item: rank.get(item["id"], len(rank)))
        if added or ordered != self.store["blueprints"]:
            self.store["blueprints"] = ordered
            self.save_store()
        for path in self.runs.glob("*/run.json") if recover_pending else []:
            run = json.loads(path.read_text())
            if run["status"] in {"queued", "running"}:
                run.update(status="interrupted", error="Server restarted before completion; submit a new run")
                self.save_run(path.parent, run)

    def save_store(self):
        temp = self.store_path.with_suffix(".tmp")
        write_json(temp, redact(self.store))
        temp.replace(self.store_path)

    def blueprint(self, data):
        item = {k: text_field(data, k) for k in BLUEPRINT_FIELDS}
        if not item["title"]:
            raise ValueError("Blueprint title is required")
        supplied_id = text_field(data, "id", maximum=64)
        with self.lock:
            old = next((x for x in self.store["blueprints"] if x["id"] == supplied_id), None)
            item.update(id=old["id"] if old else uuid.uuid4().hex, updated_utc=regen.now())
            if old:
                self.store["blueprints"][self.store["blueprints"].index(old)] = item
            else:
                self.store["blueprints"].append(item)
            self.save_store()
        return item

    def note(self, data):
        item = {k: text_field(data, k) for k in ("blueprint_id", "title", "url", "claim", "species", "confounders")}
        kind = text_field(data, "kind")
        direction = text_field(data, "direction")
        if kind not in {"anecdote", "vendor claim", "personal observation", "paper", "preprint", "other"}:
            raise ValueError("Unknown source kind")
        if direction not in {"supports", "contradicts", "mixed", "unclear"}:
            raise ValueError("Unknown claim direction")
        if not item["claim"] or (item["url"] and not public_url(item["url"])):
            raise ValueError("Supply a claim and a valid http(s) source URL, when known")
        if not any(b["id"] == item["blueprint_id"] for b in self.store["blueprints"]):
            raise ValueError("Unknown blueprint")
        item.update(id=uuid.uuid4().hex, kind=kind, direction=direction, review_status="unreviewed", recorded_utc=regen.now(), origin="manually entered; URL not fetched")
        with self.lock:
            self.store["notes"].append(item)
            self.save_store()
        return item

    def state(self):
        with self.lock:
            runs = [json.loads(p.read_text()) for p in self.runs.glob("*/run.json")]
            runs.sort(key=lambda r: r["created_utc"], reverse=True)
            return {**self.store, "findings": self.seed_findings, "runs": [{k: r.get(k) for k in ("id", "kind", "blueprint_id", "created_utc", "status", "error", "summary")} for r in runs[:100]],
                    "providers": [{"id": k, "name": v[0], "key_configured": bool(os.environ.get(v[1], "")) if v[1] else None, "key_required": v[2]} for k, v in PROVIDERS.items()],
                    "rdkit_available": importlib.util.find_spec("rdkit") is not None}

    def save_run(self, path, run):
        with self.lock:
            temp = path / "run.tmp"
            write_json(temp, redact(run))
            temp.replace(path / "run.json")

    def run(self, run_id):
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("Invalid run ID")
        with self.lock:
            return json.loads((self.runs / run_id / "run.json").read_text())

    def submit(self, data):
        kind = data.get("kind")
        if kind not in KINDS:
            raise ValueError("Unknown job type")
        blueprint_id = text_field(data, "blueprint_id", maximum=64)
        if not any(b["id"] == blueprint_id for b in self.store["blueprints"]):
            raise ValueError("Unknown blueprint")
        params = {"kind": kind, "blueprint_id": blueprint_id}
        if kind == "search":
            params["query"] = text_field(data, "query", maximum=500)
            providers = data.get("providers", ["pubmed", "europepmc", "trials"])
            if not isinstance(providers, list) or not providers or len(providers) > 8 or any(not isinstance(p, str) or p not in PROVIDERS for p in providers):
                raise ValueError("Select 1-8 known providers")
            if not params["query"]:
                raise ValueError("Search query is required")
            params.update(providers=list(dict.fromkeys(providers)), limit=bounded_int(data.get("limit", 5), 1, 10))
        elif kind in {"compound", "neighbors"}:
            params["name"] = text_field(data, "name", maximum=200)
            if not params["name"]:
                raise ValueError("Compound name or CID is required")
            params["threshold"] = bounded_int(data.get("threshold", 90), 80, 99)
        else:
            params["smiles"] = text_field(data, "smiles", maximum=2000)
            molecule(params["smiles"])
            if kind == "compare":
                params["candidate"] = text_field(data, "candidate", maximum=2000)
                molecule(params["candidate"])
            if kind == "conformers":
                params.update(seed=bounded_int(data.get("seed", 42), 0, 2147483647), conformers=bounded_int(data.get("conformers", 5), 1, 10), max_iters=500)
            if kind == "variants":
                params["max_mw"] = bounded_int(data.get("max_mw", 600), 50, 2000)
                params["max_tpsa"] = bounded_int(data.get("max_tpsa", 160), 0, 500)
        with self.lock:
            if self.pending >= 8:
                raise ValueError("Queue is full; wait for current runs")
            self.pending += 1
            run_id = uuid.uuid4().hex
            path = self.runs / run_id
            path.mkdir()
            run = {"id": run_id, "kind": kind, "blueprint_id": blueprint_id, "created_utc": regen.now(), "status": "queued", "parameters": params}
            self.save_run(path, run)
            self.executor.submit(self.execute, path, run)
        return run

    def snapshot(self, path, provider, raw):
        file = path / f"{provider}.json"
        write_json(file, redact(raw))
        receipt = regen.record("desk-fetch", {"provider": provider, "run_id": path.name, "snapshot": "JSON reserialized with configured credentials redacted"}, [file])
        return {"file": file.name, "sha256": regen.sha256_file(file), "receipt": receipt.name}

    def chemical_rows(self, path, pairs, parent=None):
        from rdkit.Chem import Draw
        rows = []
        for index, (mol, label) in enumerate(pairs):
            row = {"label": label, **describe(mol, parent)}
            filename = f"molecule-{index}.png"
            Draw.MolToImage(mol, size=(520, 320)).save(path / filename)
            row["image"] = f"/api/artifact/{path.name}/{filename}"
            rows.append(row)
        return rows

    def compute(self, path, params):
        from rdkit import Chem, rdBase
        kind = params["kind"]
        parent = molecule(params["smiles"])
        common = {"rdkit_version": rdBase.rdkitVersion, "fingerprint": "Morgan radius=2, 2048 bits, chirality enabled", "interpretation": "Computed properties and structural hypotheses; no measured activity, safety, brain exposure or rejuvenation prediction"}
        if kind == "conformers":
            with (path / "input.csv").open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "smiles"])
                writer.writerow(["candidate", Chem.MolToSmiles(parent)])
            compound_screen(["--input", str(path / "input.csv"), "--out", str(path / "conformers"), "--conformers", str(params["conformers"]), "--seed", str(params["seed"]), "--max-iters", "500"], regen.record)
            result = json.loads((path / "conformers" / "compounds.json").read_text())
            return {**common, **result, "molecules": self.chemical_rows(path, [(parent, "Input molecule")]),
                    "interpretation": "ETKDGv3 / MMFF94s conformer sampling. Relative energies only within this molecule; not docking, molecular dynamics or efficacy"}
        pairs = [(parent, "Reference")]
        if kind == "compare":
            pairs.append((molecule(params["candidate"]), "Submitted variant; unmeasured"))
        else:
            pairs.extend(enumerate_variants(parent))
        rows = self.chemical_rows(path, pairs, parent)
        for row in rows:
            row["delta"] = {k: round(row[k] - rows[0][k], 3) for k in ("mw", "logp", "tpsa", "hbd", "hba")}
            row["novelty"] = "Not checked against databases"
            if kind == "variants":
                row["passes_constraints"] = row["mw"] <= params["max_mw"] and row["tpsa"] <= params["max_tpsa"] and not row["pains"]
        return {**common, "molecules": rows, "enumeration": "Single fluoro, methyl or hydroxy replacement of aromatic C-H; up to 18 unique products. No synthesis or stability claim" if kind == "variants" else None,
                "message": "No eligible aromatic C-H sites" if kind == "variants" and len(rows) == 1 else ""}

    def compounds(self, path, params):
        from rdkit import rdBase
        name = params["name"]
        namespace = "cid" if name.isdigit() else "name"
        props = "SMILES,ConnectivitySMILES,MolecularWeight,IUPACName,Title,InChIKey"
        base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
        raw = fetch_json(base + f"{namespace}/{quote(name, safe='')}/property/{props}/JSON")
        snapshots = [self.snapshot(path, "pubchem-reference", raw)]
        records = raw.get("PropertyTable", {}).get("Properties", [])
        if not records:
            raise ProviderError("PubChem returned no compound records")
        reference = records[0]
        if params["kind"] == "neighbors":
            if len(records) > 1:
                raise ValueError("Name resolved to multiple structures; resolve the compound and use an exact CID for neighbor search")
            similar = fetch_json(base + f"fastsimilarity_2d/cid/{reference['CID']}/property/{props}/JSON?" + urlencode({"Threshold": params["threshold"], "MaxRecords": 12}))
            snapshots.append(self.snapshot(path, "pubchem-neighbors", similar))
            records = [reference] + [x for x in similar.get("PropertyTable", {}).get("Properties", []) if x.get("CID") != reference["CID"]]
        reference_smiles = reference.get("SMILES") or reference.get("IsomericSMILES")
        try:
            parent = molecule(reference_smiles)
        except ValueError:
            parent = None
        rows = []
        for record in records[:13]:
            smiles = record.get("SMILES") or record.get("IsomericSMILES")
            row = {"label": record.get("Title") or str(record["CID"]), "cid": record["CID"], "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{record['CID']}",
                   "smiles": smiles or "", "record": record, "status": "database record"}
            try:
                mol = molecule(smiles)
                computed = self.chemical_rows(path, [(mol, row["label"])], parent)[0]
                old = path / "molecule-0.png"
                dest = path / f"pubchem-{record['CID']}.png"
                old.replace(dest)
                computed["image"] = f"/api/artifact/{path.name}/{dest.name}"
                row.update(computed, status="computed descriptors")
            except ValueError as exc:
                row["status"] = str(exc)
            rows.append(row)
        return {"molecules": rows, "snapshots": snapshots, "rdkit_version": rdBase.rdkitVersion, "identity_note": "Multiple database records match this name; inspect stereochemistry and choose an exact CID" if params["kind"] == "compound" and len(records) > 1 else "",
                "interpretation": "PubChem identity and structural neighbors, not shared biological effects. PubChem similarity and local Morgan similarity use different fingerprints"}

    def execute(self, path, run):
        run["status"] = "running"
        self.save_run(path, run)
        try:
            params = run["parameters"]
            if run["kind"] == "search":
                result = {"hits": [], "providers": []}
                for provider in params["providers"]:
                    try:
                        raw, hits = search_provider(provider, params["query"], params["limit"])
                        snapshot = self.snapshot(path, provider, raw)
                        result["providers"].append({"provider": provider, "status": "ok", "count": len(hits), **snapshot})
                        for row in hits:
                            doi = (row.get("doi") or "").lower().replace("https://doi.org/", "")
                            row["duplicate_key"] = doi or row.get("pmid") or re.sub(r"\W", "", row["title"].lower())
                            row["retrieved_utc"] = regen.now()
                        result["hits"].extend(hits)
                    except (ProviderError, ValueError, KeyError, TypeError) as exc:
                        result["providers"].append({"provider": provider, "status": "error", "error": str(exc) if isinstance(exc, ProviderError) else "Unexpected provider response schema"})
                    run["result"] = result
                    self.save_run(path, run)
                successes = sum(p["status"] == "ok" for p in result["providers"])
                run["status"] = "complete" if successes == len(result["providers"]) else "partial" if successes else "failed"
                run["summary"] = f"{len(result['hits'])} source records; {successes}/{len(result['providers'])} providers succeeded"
            elif run["kind"] in {"compound", "neighbors"}:
                result = self.compounds(path, params)
                run.update(status="complete", summary=f"{len(result['molecules'])} database structures")
            else:
                result = self.compute(path, params)
                run.update(status="complete", summary=f"{len(result.get('molecules', []))} computed structures")
            run["result"] = result
            write_json(path / "result.json", redact(result))
            write_json(path / "parameters.json", params)
            manifest(path, "research-desk", params, {}, {"desk_implementation_sha256": regen.sha256_file(Path(__file__)), "rdkit": result.get("rdkit_version", "not recorded / lookup")})
            report = json.loads((path / "manifest.json").read_text())
            # Run status is mutable; the manifest covers immutable data and nested reports.
            report["outputs"].pop("run.json", None)
            for nested in path.glob("*/*"):
                if nested.is_file():
                    report["outputs"][nested.relative_to(path).as_posix()] = {"sha256": regen.sha256_file(nested), "bytes": nested.stat().st_size}
            write_json(path / "manifest.json", report)
            regen.record("desk-run", {"run_id": run["id"], "kind": run["kind"], "status": run["status"]}, [path / "manifest.json", path / "result.json"])
        except (ProviderError, ValueError) as exc:
            run.update(status="failed", error=str(exc))
        except Exception as exc:
            run.update(status="failed", error=f"{type(exc).__name__}: run failed; raw exception suppressed to protect credentials")
        finally:
            run["finished_utc"] = regen.now()
            self.save_run(path, run)
            with self.lock:
                self.pending -= 1

    def export(self, blueprint_id):
        with self.lock:
            blueprint = next(b for b in self.store["blueprints"] if b["id"] == blueprint_id)
            notes = [n for n in self.store["notes"] if n["blueprint_id"] == blueprint_id]
            runs = [json.loads(p.read_text()) for p in self.runs.glob("*/run.json")]
            runs = sorted((r for r in runs if r.get("blueprint_id") == blueprint_id), key=lambda r: r["created_utc"])
        parts = [f"# {blueprint['title']}", "Research hypothesis. Computational outputs, source reports, and demonstrated effects remain distinct."]
        for field in BLUEPRINT_FIELDS[2:]:
            parts.extend([f"## {field.replace('_', ' ').title()}", blueprint.get(field) or "Not specified"])
        findings = [f for f in self.seed_findings if f["blueprint_id"] == blueprint_id]
        parts.append("## Source-reviewed starting points")
        for finding in findings:
            parts.append(f"- {finding['claim']} {finding['boundary']} Source: {finding['url']}")
        parts.append("## Source notes (manually entered, unreviewed)")
        for note in notes:
            parts.append(f"- [{note['kind']}; {note['direction']}] {note['claim']}\n  Source: {note['url'] or 'not provided'}\n  Confounders: {note['confounders'] or 'not assessed'}")
        parts.append("## Reproducible runs")
        for run in runs:
            parts.append(f"- {run['id']} | {run['kind']} | {run['status']} | {run.get('summary', run.get('error', ''))}")
            for h in run.get("result", {}).get("hits", []):
                parts.append(f"  - {h['title']} | {h['url']} | {h['evidence_type']}")
        return {"blueprint": blueprint, "findings": findings, "notes": notes, "runs": runs, "markdown": "\n\n".join(parts), "exported_utc": regen.now()}


def make_handler(desk):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RegenDesk/1"

        def log_message(self, *_):
            pass

        def send(self, status, data, content_type="application/json"):
            if content_type == "application/json" and not isinstance(data, bytes):
                data = json.dumps(data, allow_nan=False).encode()
            if isinstance(data, str):
                data = data.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self, mutation=False):
            host = self.headers.get("Host", "")
            if not re.fullmatch(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", host):
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}", f"https://{host}"}:
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return False
            return not mutation or self.headers.get("Content-Type", "").split(";")[0] == "application/json"

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {"error": "Local same-origin requests only"})
            route = urlsplit(self.path).path
            try:
                if route == "/api/state":
                    return self.send(200, desk.state())
                if route.startswith("/api/run/"):
                    return self.send(200, desk.run(route.rsplit("/", 1)[1]))
                if route.startswith("/api/export/"):
                    return self.send(200, desk.export(route.rsplit("/", 1)[1]))
                if route.startswith("/api/artifact/"):
                    relative = route.removeprefix("/api/artifact/")
                    path = (desk.runs / relative).resolve()
                    if not path.is_relative_to(desk.runs.resolve()) or path.suffix not in {".json", ".png", ".csv", ".sdf", ".md"}:
                        return self.send(403, {"error": "Artifact path is not allowed"})
                    return self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                static = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}.get(route)
                if static:
                    return self.send(200, (STATIC / static).read_bytes(), {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript", "style.css": "text/css"}[static])
                self.send(404, {"error": "Not found"})
            except (FileNotFoundError, StopIteration):
                self.send(404, {"error": "Record not found"})
            except ValueError as exc:
                self.send(400, {"error": str(exc)})

        def do_POST(self):
            if not self.allowed(True):
                return self.send(403, {"error": "Local same-origin JSON requests only"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 64000:
                    return self.send(413, {"error": "Request must be 1-64000 bytes"})
                self.connection.settimeout(10)
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                route = urlsplit(self.path).path
                action = {"/api/jobs": desk.submit, "/api/blueprints": desk.blueprint, "/api/notes": desk.note}.get(route)
                if not action:
                    return self.send(404, {"error": "Not found"})
                self.send(202 if route == "/api/jobs" else 200, action(data))
            except (ValueError, TypeError) as exc:
                self.send(400, {"error": str(exc)})
            except Exception:
                self.send(500, {"error": "Request could not be saved"})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "run"])
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "0.0.0.0"])
    parser.add_argument("--port", type=int, default=8092)
    parser.add_argument("--request", type=Path, help="JSON request file for a reproducible CLI run")
    args = parser.parse_args()
    if args.command == "serve":
        server = ThreadingHTTPServer((args.host, args.port), BaseHTTPRequestHandler)
        desk = Desk(recover_pending=True)
        server.RequestHandlerClass = make_handler(desk)
        print(f"Regen research desk: http://127.0.0.1:{args.port}")
        server.serve_forever()
    else:
        if not args.request:
            parser.error("run requires --request")
        # CLI dispatches to the single running service so recovery and writes have one owner.
        endpoint = f"http://127.0.0.1:{args.port}"
        request = Request(endpoint + "/api/jobs", data=args.request.read_bytes(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=15) as response:
            finished = json.load(response)
        while finished["status"] in {"queued", "running"}:
            time.sleep(1)
            with urlopen(endpoint + "/api/run/" + finished["id"], timeout=15) as response:
                finished = json.load(response)
        print(json.dumps({k: finished.get(k) for k in ("id", "status", "summary", "error")}, indent=2))
        if finished["status"] in {"failed", "interrupted"}:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
