"""Print one version's section of CHANGELOG.md (used for GitHub release notes).

python3 scripts/changelog_section.py 0.3.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def section(text: str, version: str) -> str:
    """Body of the ``## [version]`` section, without the heading."""
    heading = re.compile(rf"^## \[{re.escape(version)}\].*$", re.MULTILINE)
    match = heading.search(text)
    if not match:
        raise SystemExit(f"CHANGELOG.md has no section for version {version}")
    rest = text[match.end() :]
    nxt = re.search(r"^## \[|^\[[^\]]+\]: ", rest, re.MULTILINE)
    return rest[: nxt.start() if nxt else len(rest)].strip() + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    print(section(CHANGELOG.read_text(), argv[1]), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
