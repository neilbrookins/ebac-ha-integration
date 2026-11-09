"""The Python packages the tests need beyond Home Assistant itself, printed
for pip: those of the integrations EBaC depends on (conversation, tts, and
theirs), and of the others the tests set up, at the versions the Home
Assistant installed pins them to.

Home Assistant installs an integration's requirements when it is set up;
the tests can't, so they're installed first (see .github/workflows/tests.yml):

    pip install -r <(python tools/test_requirements.py)
"""

from __future__ import annotations

import json
from pathlib import Path

import homeassistant.components

COMPONENTS = Path(homeassistant.components.__file__).parent
EBAC = Path(__file__).parent.parent / "custom_components" / "ebac" / "manifest.json"
# Set up by the tests themselves, beside EBaC's dependencies
ALSO = ["homeassistant", "conversation", "repairs", "assist_satellite", "notify"]


def manifest(domain: str) -> dict:
    path = COMPONENTS / domain / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    ebac = json.loads(EBAC.read_text(encoding="utf-8"))
    to_do = [*ebac.get("dependencies", []), *ALSO]
    done: set[str] = set()
    requirements: list[str] = [*ebac.get("requirements", [])]
    while to_do:
        domain = to_do.pop()
        if domain in done:
            continue
        done.add(domain)
        found = manifest(domain)
        requirements.extend(found.get("requirements", []))
        to_do.extend(found.get("dependencies", []))
        to_do.extend(found.get("after_dependencies", []))
    for requirement in sorted(set(requirements)):
        print(requirement)


if __name__ == "__main__":
    main()
