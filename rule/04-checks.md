# 04. Checks before finishing any change

Run all three and fix every error:

```bash
python tools/build_catalog.py
python tools/validate_skills.py
python tools/build_catalog.py --check
```

CI also runs:

```bash
python -m compileall -q tools skills mcp-server
python -m unittest discover -s mcp-server/tests -v
python -m unittest discover -s skills/<name>/scripts -p "test_*.py" -v
```

`image-inspector` and `video-inspector` tests need `Pillow` and `opencv-python-headless`. All other tests are stdlib only.
