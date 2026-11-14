# 05. Tooling

1. Tooling is **Python standard library only**. Do not add dependencies to `tools/`.
2. `tools/install.py` must stay compatible with Python 3.8 (CI checks with `vermin`).
3. `install.py` must never write without the user's confirmation (or `--yes`).
4. Test `install.py` with a sandboxed home: set `HOME` and `USERPROFILE` to a temp folder.
5. Do not publish the hub to GitHub Pages. Link repo files instead.
