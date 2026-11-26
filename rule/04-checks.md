# 04. Checks before finishing any change

Run this and fix every failure:

```bash
python tools/hub.py check            # or --changed while iterating
```

It runs, in parallel, everything listed below and prints only the failures. Separately:

```bash
python tools/build_catalog.py
python tools/validate_skills.py
python tools/build_catalog.py --check
```

CI also runs:

```bash
python -m compileall -q tools skills mcp-server skill-hub-mcp
python -m unittest discover -s mcp-server/tests -v
python -m unittest discover -s skill-hub-mcp/tests -v
python -m unittest discover -s tools -p "test_*.py" -v
python -m unittest discover -s skills/<area>/<group>/<name>/scripts -p "test_*.py" -v
```

Skill tests need no Python packages. `video-inspector` frame tests need the ffmpeg program and are skipped without it; with Pillow or OpenCV installed, extra tests check the results against them.
