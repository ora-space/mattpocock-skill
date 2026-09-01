# Matt Pocock Skills for Ora

This repository packages the public **Mattpocock Skills** group from
[`mattpocock/skills`](https://github.com/mattpocock/skills) as a static Ora
Skill plugin.

The group is not inferred from every `SKILL.md` in the upstream repository.
It is the exact set explicitly listed in upstream's
`.claude-plugin/plugin.json`. That is also the manifest used by
`npx skills add mattpocock/skills` to present the single **Mattpocock Skills**
group. At release `v1.2.3`, the group contains 25 skills; experimental and
miscellaneous skills not named by the manifest are intentionally excluded.

## Package layout

Upstream organizes skills by category, for example
`skills/engineering/tdd`. Ora Skill plugins require a flat contribution
layout, so packaging projects each selected directory to `assets/<name>` while
preserving all files inside that skill package:

```text
orax.toml
assets/
  tdd/
    SKILL.md
    tests.md
  writing-for-agents/
    SKILL.md
```

The plugin identifier is `mattpocock.skills`; its marketplace identity is
`official/mattpocock.skills`.

## Build and verify

Python 3 and Git are the only build requirements.

```bash
python3 scripts/package.py \
  --upstream-tag v1.2.3 \
  --repository ora-space/mattpocock-skill
python3 scripts/validate_package.py \
  dist/mattpocock.skills-v1.2.3.orax \
  --expected-version 1.2.3 \
  --expected-count 25
```

The package script reads the upstream group manifest, verifies every selected
skill, produces a deterministic `.orax`, and writes the release-form marketplace
manifest to `dist/manifest.toml`.

## Automated releases

`.github/workflows/sync-release.yml` checks the latest upstream GitHub release
every day. If this repository does not already have a release with the same
tag, it rebuilds and validates the plugin, creates that release, and opens an
update PR in `ora-space/marketplace`.

Cross-repository PR creation requires a repository secret named
`MARKETPLACE_TOKEN` with permission to push a branch and open a pull request in
`ora-space/marketplace`.

## License

The packaging code is MIT licensed. Packaged skills retain Matt Pocock's
upstream MIT license, included as `UPSTREAM_LICENSE` in every `.orax`.
