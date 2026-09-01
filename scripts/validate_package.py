#!/usr/bin/env python3
"""Validate the static Skill plugin invariants of an Ora .orax package."""

from __future__ import annotations

import argparse
import re
import tempfile
import tomllib
import zipfile
from pathlib import Path


NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-count", type=int)
    return parser.parse_args()


def frontmatter(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8")
    if len(raw.encode()) > 1024 * 1024 or not raw.startswith("---\n"):
        raise ValueError(f"invalid front matter or size: {path}")
    end = raw.find("\n---", 4)
    if end < 0:
        raise ValueError(f"unterminated front matter: {path}")
    header = raw[4:end]
    values: dict[str, str] = {}
    for field in ("name", "description"):
        match = re.search(rf"^{field}\s*:\s*(.+?)\s*$", header, re.MULTILINE)
        if match is None:
            raise ValueError(f"missing {field}: {path}")
        values[field] = match.group(1).strip().strip('"\'').strip()
    return values["name"], values["description"]


def main() -> None:
    args = arguments()
    if not zipfile.is_zipfile(args.package):
        raise ValueError(f"not a ZIP-format .orax: {args.package}")
    with tempfile.TemporaryDirectory(prefix="validate-orax-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(args.package) as archive:
            for entry in archive.infolist():
                target = (root / entry.filename).resolve()
                if not target.is_relative_to(root.resolve()):
                    raise ValueError(f"archive path escapes package: {entry.filename}")
            archive.extractall(root)

        manifest = tomllib.loads((root / "orax.toml").read_text(encoding="utf-8"))
        expected = {
            "resolver": 1,
            "identifier": "mattpocock.skills",
            "namespace": "official",
            "kind": "skill",
            "version": args.expected_version,
        }
        for field, value in expected.items():
            if manifest.get(field) != value:
                raise ValueError(f"manifest {field} is {manifest.get(field)!r}, expected {value!r}")
        if (root / "main.js").exists():
            raise ValueError("static Skill plugin must not ship main.js")

        assets = root / "assets"
        skill_dirs = sorted(path for path in assets.iterdir() if path.is_dir())
        if not skill_dirs or any(path.is_file() for path in assets.iterdir()):
            raise ValueError("assets must contain only direct skill directories")
        if args.expected_count is not None and len(skill_dirs) != args.expected_count:
            raise ValueError(f"found {len(skill_dirs)} skills, expected {args.expected_count}")
        seen: set[str] = set()
        for skill_dir in skill_dirs:
            name, description = frontmatter(skill_dir / "SKILL.md")
            if not NAME.fullmatch(name) or name.lower() != skill_dir.name.lower() or not description:
                raise ValueError(f"invalid skill identity in {skill_dir}")
            canonical = name.lower()
            if canonical in seen:
                raise ValueError(f"duplicate skill name: {name}")
            seen.add(canonical)
        print(f"validated {args.package}: {len(skill_dirs)} skills, version {args.expected_version}")


if __name__ == "__main__":
    main()
