"""Build a static, explicitly curated ResearchDesk edition without local state."""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

import research_progress as progress

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/dylanstechmann/regen-workbench"
ASSETS = Path(__file__).resolve().parent / "public_desk"


def page(title, body, *, prefix="./", script=False):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Inspect regeneration research, its evidence limits and the next useful analyses.">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>{escape(title)} · Regen Research Desk</title>
<link rel="stylesheet" href="{prefix}style.css">
{f'<script src="{prefix}app.js" defer></script>' if script else ''}</head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="app-header"><a class="brand" href="{prefix}index.html"><span class="brand-mark" aria-hidden="true">R</span><strong>REGEN</strong><span>Research desk</span></a>
<div class="header-meta"><span class="public-label">Public edition</span><a href="{REPOSITORY}">Repository ↗</a></div></header>
{body}
<footer>Personal research project, developed with substantial AI assistance. Evidence labels describe the analysis, not proof of restoration or rejuvenation.</footer>
</body></html>\n'''


def _source_url(revision, path):
    return f"{REPOSITORY}/blob/{revision}/{quote(path, safe='/')}"


def build(output, *, repo_root=ROOT, revision):
    """Fail closed before writing if any declared artifact changed; never scan data/."""
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("An exact Git commit SHA is required for source links")
    repo_root, output = Path(repo_root).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a new directory; existing files are never replaced")
    rows = progress._document(repo_root)
    if not rows:
        raise ValueError("A public edition requires at least one curated entry")
    # Read and verify the whole allowlist first. No recursive study or workspace copy.
    verified = {(row["id"], a["id"]): progress._artifact_bytes(repo_root, a)
                for row in rows for a in row["artifacts"]}
    topics = Counter(row["topic"] for row in rows)
    latest = max(row["updated_on"] for row in rows)
    topic_options = ''.join(f'<option value="{escape(t, quote=True)}">{escape(t)} ({n})</option>'
                            for t, n in sorted(topics.items()))
    kinds = sorted({row["evidence_kind"] for row in rows})
    kind_options = ''.join(f'<option value="{k}">{escape(progress.KINDS[k])}</option>' for k in kinds)
    cards, documents, manifest_rows = [], {}, []
    for row in rows:
        ident = row["id"]
        links, artifacts = [], []
        for artifact in row["artifacts"]:
            aid = artifact["id"]
            stem = f"artifacts/{ident}/{aid}"
            source = _source_url(revision, artifact["path"])
            content = verified[ident, aid]
            back = f"../../index.html#{ident}"
            documents[stem + ".txt"] = content
            body = f'''<main id="main" class="document-page">
<a class="back" href="{back}">← Back to research entry</a>
<p class="eyebrow">{escape(row['topic'])} / {escape(progress.KINDS[row['evidence_kind']])}</p>
<h1>{escape(artifact['label'])}</h1><p class="document-context">{escape(row['title'])}</p>
<p class="boundary">{escape(row['boundary'])}</p>
<nav class="document-actions" aria-label="Document actions"><a href="{aid}.txt" download>Download original text</a><a href="{source}">Formatted source on GitHub ↗</a></nav>
<p class="document-meta">Source: <code>{escape(artifact['path'])}</code><br>SHA-256 of UTF-8 text with LF line endings: <code>{artifact['sha256_lf_text']}</code></p>
<pre class="document">{escape(content.decode('utf-8'))}</pre></main>'''
            documents[stem + ".html"] = page(artifact["label"], body, prefix="../../").encode("utf-8")
            links.append(f'<a href="./{stem}.html">{escape(artifact["label"])} <span aria-hidden="true">↗</span></a>')
            artifacts.append({"id": aid, "label": artifact["label"], "path": artifact["path"],
                              "sha256_lf_text": artifact["sha256_lf_text"], "bytes_utf8_lf": len(content),
                              "reader": stem + ".html", "download": stem + ".txt", "source": source})
        cards.append(f'''<article class="research-card" id="{ident}" data-topic="{escape(row['topic'], quote=True)}" data-kind="{row['evidence_kind']}">
<div class="card-meta"><span>{escape(row['topic'])}</span><time datetime="{row['updated_on']}">{row['updated_on']}</time></div>
<p class="evidence-tag kind-{row['evidence_kind']}">{escape(progress.KINDS[row['evidence_kind']])}</p>
<h3><a class="entry-link" href="#{ident}">{escape(row['title'])}</a></h3>
<p class="result">{escape(row['result'])}</p>
<div class="boundary"><h4>Limits of this result</h4><p>{escape(row['boundary'])}</p></div>
<div class="next-step"><h4>Next useful step</h4><p>{escape(row['next_step'])}</p></div>
<nav class="artifact-links" aria-label="Files for {escape(row['title'], quote=True)}">{''.join(links)}</nav></article>''')
        manifest_rows.append({key: row[key] for key in ["id", "title", "topic", "updated_on", "evidence_kind", "result", "boundary", "next_step"]}
                             | {"evidence_label": progress.KINDS[row["evidence_kind"]], "artifacts": artifacts})
    body = f'''<main id="main" class="dashboard">
<section class="intro" aria-labelledby="intro-title"><div><p class="eyebrow">REGENERATION / DURABLE YOUTHFUL FUNCTION</p>
<h1 id="intro-title">Restoration research,<br>with the evidence in view.</h1>
<p>Explore work toward restoring natural teeth, gums and living attachment, alongside genome repair, stem cells, organoids and youthful function throughout the body.</p></div>
<dl class="snapshot"><div><dt>Research entries</dt><dd>{len(rows)}</dd></div><div><dt>Research areas</dt><dd>{len(topics)}</dd></div><div><dt>Latest entry</dt><dd class="date">{latest}</dd></div></dl></section>
<div class="scope-note"><strong>Research in progress.</strong> Published-data analyses, source audits, plans and illustrative models retain separate labels. None establishes complete tooth regeneration or durable human rejuvenation.</div>
<section aria-labelledby="entries-title"><div class="section-heading"><div><p class="eyebrow">THE RESEARCH CHECKLIST</p><h2 id="entries-title">Progress and next questions</h2></div><p id="result-count" role="status">{len(rows)} entries</p></div>
<div class="filters" id="filters" hidden><label>Research area<select id="topic"><option value="">All research areas</option>{topic_options}</select></label>
<label>Evidence type<select id="kind"><option value="">All evidence types</option>{kind_options}</select></label>
<label class="search">Find in entries<input id="query" type="search" placeholder="Enamel, ligament, delivery…" maxlength="300"></label><button id="clear" type="button">Clear filters</button></div>
<noscript><p>All entries and reports are available below. Enable JavaScript to filter them.</p></noscript>
<p id="no-results" class="empty" hidden>No entries match these filters. Try another term or clear the filters.</p>
<div class="card-grid">{''.join(cards)}</div></section>
<section class="about" aria-labelledby="about-title"><div><p class="eyebrow">ABOUT THIS EDITION</p><h2 id="about-title">A public window into the research</h2>
<p>This site contains the curated progress catalog and its linked reports and result files. Share an entry by opening its title and copying the page address. Reports are included as text, with links to their formatted source on GitHub.</p></div>
<div><h3>The full workbench runs locally</h3><p>Live literature searches, chemistry jobs, saved notes and editable studies need the ResearchDesk service. This public edition does not connect to your computer or include saved workspace data.</p>
<a href="{_source_url(revision, 'PUBLIC_RESEARCH_DESK.md')}">Hosting and update details ↗</a><p class="document-meta">Source revision <a href="{REPOSITORY}/commit/{revision}"><code>{revision[:12]}</code></a> · <a href="./catalog.json" download>Download catalog</a></p></div></section>
</main>'''
    documents["index.html"] = page("Research progress", body, script=True).encode("utf-8")
    documents["catalog.json"] = (json.dumps({"schema_version": 1, "source_revision": revision,
        "count": len(rows), "updates": manifest_rows}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for asset in ["style.css", "app.js"]:
        documents[asset] = (ASSETS / asset).read_bytes()
    documents[".nojekyll"] = b""
    # Stage in the same parent so an unsuccessful build cannot leave a partial site.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="public-desk-", dir=output.parent) as temporary:
        staged = Path(temporary) / "site"
        staged.mkdir()
        for name, content in documents.items():
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        staged.rename(output)
    return {"entries": len(rows), "artifacts": len(verified), "files": len(documents), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--revision", required=True, help="Exact public source commit SHA")
    args = parser.parse_args()
    print(json.dumps(build(args.output, revision=args.revision)))


if __name__ == "__main__":
    main()
