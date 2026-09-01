#!/usr/bin/env python3
"""Build the upstream Mattpocock Skills plugin as a deterministic .orax."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "https://github.com/mattpocock/skills.git"
PLUGIN_MANIFEST = Path(".claude-plugin/plugin.json")
PLUGIN_IDENTIFIER = "mattpocock.skills"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-tag", required=True)
    parser.add_argument("--repository", required=True, help="GitHub owner/repository for release URLs")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    return parser.parse_args()


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def scalar(frontmatter: str, field: str) -> str:
    match = re.search(rf"^{re.escape(field)}\s*:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if match is None:
        raise ValueError(f"SKILL.md has no scalar {field}")
    value = match.group(1)
    if value[:1] in {'"', "'"}:
        value = ast.literal_eval(value)
    return str(value).strip()


def validate_skill(skill_dir: Path) -> str:
    manifest = skill_dir / "SKILL.md"
    if not manifest.is_file():
        raise ValueError(f"selected skill has no SKILL.md: {skill_dir}")
    raw = manifest.read_text(encoding="utf-8")
    if len(raw.encode()) > 1024 * 1024 or not raw.startswith("---\n"):
        raise ValueError(f"invalid SKILL.md front matter or size: {manifest}")
    end = raw.find("\n---", 4)
    if end < 0:
        raise ValueError(f"unterminated SKILL.md front matter: {manifest}")
    frontmatter = raw[4:end]
    name = scalar(frontmatter, "name")
    description = scalar(frontmatter, "description")
    if not description or len(description.encode()) > 4096:
        raise ValueError(f"invalid skill description: {manifest}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError(f"invalid skill name {name!r}: {manifest}")
    if name.lower() != skill_dir.name.lower():
        raise ValueError(f"skill name {name!r} does not match directory {skill_dir.name!r}")
    return name.lower()


def replace_version(manifest: str, version: str) -> str:
    updated, count = re.subn(
        r'^version\s*=\s*"[^"]+"\s*$',
        f'version = "{version}"',
        manifest,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("orax.toml must contain exactly one version field")
    return updated.rstrip() + "\n"


def add_tree(archive: zipfile.ZipFile, root: Path) -> None:
    for source in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = source.relative_to(root).as_posix()
        info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, source.read_bytes())


def main() -> None:
    args = arguments()
    tag = args.upstream_tag
    version = tag.removeprefix("v")
    if tag != f"v{version}" or SEMVER.fullmatch(version) is None:
        raise ValueError(f"upstream tag must be v-prefixed SemVer, got {tag!r}")

    args.output.mkdir(parents=True, exist_ok=True)
    for stale in (args.output / "stage", args.output / "upstream"):
        shutil.rmtree(stale, ignore_errors=True)

    with tempfile.TemporaryDirectory(prefix="mattpocock-skills-") as temporary:
        upstream = Path(temporary) / "upstream"
        run("git", "clone", "--depth", "1", "--branch", tag, UPSTREAM, str(upstream))
        manifest = json.loads((upstream / PLUGIN_MANIFEST).read_text(encoding="utf-8"))
        if manifest.get("name") != "mattpocock-skills":
            raise ValueError("unexpected upstream plugin name")
        if manifest.get("version") != version:
            raise ValueError(
                f"upstream plugin version {manifest.get('version')!r} does not match tag {tag!r}"
            )
        selected = manifest.get("skills")
        if not isinstance(selected, list) or not selected:
            raise ValueError("upstream plugin manifest has no skills list")

        stage = Path(temporary) / "stage"
        assets = stage / "assets"
        assets.mkdir(parents=True)
        seen: set[str] = set()
        upstream_root = upstream.resolve()
        for item in selected:
            if not isinstance(item, str) or not item.startswith("./skills/"):
                raise ValueError(f"unsafe or unexpected upstream skill path: {item!r}")
            source = (upstream / item).resolve()
            if not source.is_relative_to(upstream_root) or not source.is_dir():
                raise ValueError(f"upstream skill path escapes or is missing: {item!r}")
            canonical_name = validate_skill(source)
            if canonical_name in seen:
                raise ValueError(f"duplicate skill name: {canonical_name}")
            seen.add(canonical_name)
            shutil.copytree(source, assets / source.name, symlinks=False)

        (stage / "orax.toml").write_text(
            replace_version((ROOT / "orax.toml").read_text(encoding="utf-8"), version),
            encoding="utf-8",
        )
        shutil.copy2(ROOT / "README.md", stage / "README.md")
        shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
        shutil.copy2(upstream / "LICENSE", stage / "UPSTREAM_LICENSE")

        package_name = f"{PLUGIN_IDENTIFIER}-{tag}.orax"
        package = args.output / package_name
        with zipfile.ZipFile(package, "w") as archive:
            add_tree(archive, stage)

    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    release_url = f"https://github.com/{args.repository}/releases/download/{tag}/{package_name}"
    release_manifest = replace_version((ROOT / "orax.toml").read_text(encoding="utf-8"), version)
    release_manifest += f'\nurl = "{release_url}"\nsha256 = "{digest}"\n'
    (args.output / "manifest.toml").write_text(release_manifest, encoding="utf-8")
    (args.output / "skills.txt").write_text("\n".join(sorted(seen)) + "\n", encoding="utf-8")
    print(f"packaged {package} with {len(seen)} skills")
    print(f"sha256 {digest}")


if __name__ == "__main__":
    main()
