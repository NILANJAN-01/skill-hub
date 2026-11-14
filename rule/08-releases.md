# 08. Releases

1. The version is `metadata.version` in `.claude-plugin/marketplace.json`.
2. Pushing a matching `v*` tag runs `.github/workflows/release.yml` (steps in CONTRIBUTING.md).
3. `install.py` has a `DEFAULT_REF` line that the release workflow rewrites to the tag. Do not rename it.
4. Forks use `--repo` or `SKILLHUB_REPO`.
