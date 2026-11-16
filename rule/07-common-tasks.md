# 07. Common tasks

| Task | Steps |
|---|---|
| Add a skill | `cp -r template skills/<area>/<group>/<name>`, write `SKILL.md`, add to a plugin in `marketplace.json`, add prompts, rebuild and validate |
| Add a category | New plugin entry in `marketplace.json` + title in `CATEGORY_TITLES` |
| Support a new agent | Add an entry to `AGENTS` in `tools/install.py` from official docs (`project`, `global`, `also_reads`, `global_also_reads`, and `detect`), rebuild, check with `python tools/install.py --detect` |
| Generate skills from a PDF | Follow `skills/generic/hub/skillforge/SKILL.md` |
| Add a group | Create the folder `skills/<area>/<group>/`; nothing to register |
| Add an area | Add it to `AREAS` in `tools/hublib.py`, create `skills/<area>/` (with a `README.md` if empty), rebuild |
| Move a skill | `git mv` its folder, update its path in `marketplace.json`, rebuild and validate |
| Change user-facing install steps | Edit `GUIDE.md` and the README Install section |
| Browse the catalog locally | `python -m http.server`, open http://localhost:8000 |
