# Public ResearchDesk on GitHub Pages

ResearchDesk has a static public edition and a local working edition. The
public edition can run on GitHub Pages without a Python server or a connection
to the owner's computer. Its intended address is
<https://dylanstechmann.github.io/regen-workbench/> once Pages is enabled and
the deployment succeeds.

## What is published

The public edition contains only the entries explicitly listed in
`tools/data/research-progress.json` and their declared, matching study text
files. Each entry keeps its evidence type, limits and next useful step. Reports
and JSON/CSV/TSV results have a text reader, original-text download and a link
to their source at the exact build commit. Readers can filter entries by area,
evidence type and text; filters and entry links can be shared in the address.
All entries and reports remain readable with JavaScript disabled.

The builder checks every declared artifact's canonical UTF-8/LF size and SHA-256
before writing anything. A changed or missing artifact fails the whole new build.
The previously deployed snapshot remains online until a replacement succeeds;
its displayed source revision identifies that older snapshot. These checks
establish file integrity, not biological validity or human benefit.

No recursive directory export occurs. The build does not open the local Desk
store, personal notes, API credentials, caches, uncurated studies, raw source
downloads or sibling-repository artifacts. Exported reports are already part
of the public repository. Adding an artifact to the catalog is a publishing
decision: review its full content before adding or updating its pin.

## What needs a server

The complete app at <http://127.0.0.1:8092/> uses Python routes and writable local
storage for searches, chemistry jobs, campaign/blueprint/observation editing,
study-design records, run history and dossier exports. GitHub Pages cannot run
that backend. The public edition has no backend controls, API calls, browser
storage, analytics or remote dependencies; it does not try to reach localhost.

To host the complete app later, deploy a separately secured backend and connect
the frontend to it. Authentication, per-user storage, provider credentials,
job execution and resource limits would need explicit hosted designs. Exposing
the current local service directly is not the deployment mechanism here.

GitHub documents [Pages as static hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
and [custom Actions deployment](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Build and inspect locally

From this repository, supply an exact public source commit and a new output
directory. The builder deliberately never overwrites an existing directory.

```powershell
$researchRevision = git rev-parse HEAD
python -B tools/build_public_desk.py --output tmp/public-desk-preview --revision $researchRevision
python -m http.server 8093 --bind 127.0.0.1 --directory tmp/public-desk-preview
```

Open <http://127.0.0.1:8093/>. A local build from modified files is a preview;
its source links point to the supplied commit and only match after those
changes are committed. Deployment builds run from a clean checked-out commit.

## Publish and update

The workflow `.github/workflows/public-desk.yml` builds and uploads only the
generated `public-site/` directory. It does not upload the repository root.
It runs the export-boundary tests, pins source links to `GITHUB_SHA`, and
deploys with GitHub's Pages actions using `pages: write` and `id-token: write`
only in the deployment job. No personal token or research API key is needed.

In repository **Settings → Pages → Build and deployment → Source**, choose
**GitHub Actions**. Run **Publish public ResearchDesk** in Actions or push a
relevant change to `main`. Confirm the deployment succeeded before treating
the intended address as live. Deployment uses the `github-pages` environment;
the repository owner can restrict that environment to `main`.

To update the public research, review and update the curated catalog and its
artifact pins, then push to `main`. Changes under `studies/` also trigger a build
so a stale pin stops publication. The source catalog remains shared with the
local Desk; the public frontend is separate because the working frontend
depends on server APIs and absolute local routes.

Validation:

```powershell
python -B -m unittest discover -s tests -p test_public_desk.py -v
node --check tools/public_desk/app.js
python -B -m unittest discover -s tests -v
```

## Compare catalog revisions offline

Use two versions of the curated source catalog to see which findings, evidence
labels, stated limits, next steps and file pins changed. For example, from the
repository root in a POSIX shell, save a historical catalog to a temporary file
and compare it with the current one.

```sh
previous_catalog=$(mktemp)
git show 5fdcf38:tools/data/research-progress.json > "$previous_catalog"
python3 -B tools/compare_progress.py "$previous_catalog" tools/data/research-progress.json
```

The command matches stable entry and artifact IDs and reports old and new values.
Reordering entries or files has no effect. A changed SHA-256 identifies a new
text pin even when the summary still reads the same. The comparison reads only
the two supplied catalogs. The public site builder separately verifies the
linked files when creating a snapshot.

Add `--verify-after-root .` to check every declared artifact in the newer catalog against the current checkout using the public builder’s canonical UTF-8/LF rules. The JSON includes the number checked and identifies stale or unavailable files by entry and artifact ID. A stale or unavailable file gives exit status 1 alongside the metadata comparison.
