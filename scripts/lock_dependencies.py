"""Record the verified active runtime, including inherited numerical packages."""

from importlib.metadata import distribution
from pathlib import Path
import platform

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def main():
    roots = []
    for line in (ROOT / "backend/requirements.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            roots.append(Requirement(line).name)
    seen = {}

    def visit(name, extras=()):
        package = distribution(name)
        key = package.metadata["Name"]
        # Include each package/extras combination once, including uvicorn[standard].
        marker_key = (key.lower(), tuple(sorted(extras)))
        if marker_key in visited:
            return
        visited.add(marker_key)
        seen[key.lower()] = (key, package.version)
        for entry in package.requires or []:
            requirement = Requirement(entry)
            contexts = ["", *extras]
            if requirement.marker is None or any(requirement.marker.evaluate({"extra": extra}) for extra in contexts):
                visit(requirement.name, requirement.extras)

    visited = set()
    for name in roots:
        visit(name)
    content = "# Verified on Windows with Python " + platform.python_version() + "\n"
    content += "# Includes inherited packages; use an isolated venv on a new machine.\n"
    content += "\n".join(name + "==" + number for name, number in sorted(seen.values(), key=lambda item: item[0].lower())) + "\n"
    (ROOT / "backend/requirements-lock.txt").write_text(content, encoding="utf-8")
    print(f"Locked {len(seen)} verified runtime/test packages.")


if __name__ == "__main__":
    main()
