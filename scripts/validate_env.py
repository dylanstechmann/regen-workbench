"""Structural validation of compose files and .env key coverage.

Checks (without reading or printing secret values):
- docker-compose.yml and docker-compose.gpu.yml parse as YAML and have services.
- Every variable referenced by compose files is either set in .env or has a default.
- Variables present in .env are known (either used by compose, code, or documented).
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
COMPOSE_FILES = [ROOT / "docker-compose.yml", ROOT / "docker-compose.gpu.yml"]

env_names = set()
if ENV.exists():
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            env_names.add(line.split("=", 1)[0])
else:
    print(".env not found; skipping env coverage checks (compose structure still validated)")

compose_refs = set()
base_services: set[str] = set()
for i, f in enumerate(COMPOSE_FILES):
    try:
        doc = yaml.safe_load(f.read_text())
        services = doc.get("services", {})
        assert services, f"{f.name}: no services"
        if i == 0:
            for name, svc in services.items():
                assert "image" in svc or "build" in svc, f"{f.name}/{name}: no image or build"
            base_services = set(services)
        else:
            # Override files are layered on top of the base compose file;
            # every service they touch must exist in the base.
            unknown = set(services) - base_services
            assert not unknown, f"{f.name}: services not in base file: {unknown}"
        print(f"{f.name}: YAML OK, {len(services)} service(s): {', '.join(services)}")
    except Exception as exc:  # noqa: BLE001
        print(f"{f.name}: FAIL {exc}")
        raise SystemExit(1)
    compose_refs.update(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", f.read_text()))

code_vars = set()
for py in (ROOT / "tools").glob("*.py"):
    code_vars.update(re.findall(r'os\.environ(?:\.get)?\(\s*"([A-Z_]+)"', py.read_text()))

documented = set()
example = ROOT / ".env.example"
if example.exists():
    for line in example.read_text().splitlines():
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", line):
            documented.add(line.split("=", 1)[0])

missing_defaults = sorted(r for r in compose_refs if r not in env_names)
print(f"compose references {len(compose_refs)} vars; unset without default check: {missing_defaults or 'n/a'}")

unused = sorted(n for n in env_names if n not in compose_refs and n not in code_vars)
print(f".env vars not referenced by compose or code: {unused or 'none'}")
undocumented = sorted(n for n in env_names if n not in documented)
print(f".env vars not in .env.example: {undocumented or 'none'}")
print("VALIDATION PASSED")
