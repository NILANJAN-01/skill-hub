# yt-lecture MCP server

`scripts/yt_lecture_mcp.py` is a stdio MCP server (JSON-RPC 2.0, one message per line) built only on the Python standard library. It runs the same code as `yt_lecture.py`, so the guardrail cannot be skipped through it.

## Tools

| Tool | Writes files | What it does |
|---|---|---|
| `yt_check_video(url)` | no | Validates the link, reads the real title, length, category and chapters, and returns `allowed` with the reason |
| `yt_fetch_overview(url, out_dir?, source?, clip?, lang?, engine?, model?, keep_audio?, transcript_file?, redraft?)` | yes | For an allowed video, extracts the audio, analyses it and turns the speech into text (`source`: `audio` default, `audio-only`, or `captions`), then writes the folder (transcript, draft notes, `overview.md`, `overview.html`). Returns the paths, `audio_summary`, `warnings` and the first 4,000 characters of the transcript. A blocked video returns an error starting `BLOCKED`, and no audio is fetched |
| `yt_read_transcript(folder, offset?, limit?)` | no | Pages through `transcript.txt` (default 40,000 characters a page; follow `next_offset`) |
| `yt_render_overview(folder, notes?)` | yes | Merges your notes (summary, key_takeaways, sections, terms, prerequisites, further_study, review_questions) into `notes.json`, marks them `written_by: agent`, and rebuilds the Markdown and HTML |

The usual flow is check, then fetch, then read the transcript, then render with notes.

## Start it

```bash
python <skill-folder>/scripts/yt_lecture_mcp.py --out <folder for overviews> --audio-python <python with the audio packages>
```

- `--out` is the default parent folder for `yt_fetch_overview` (default: `./yt-lecture`, relative to the folder the client starts the server in). Use an absolute path so the files always land in the same place.
- `--audio-python` is the interpreter that has `yt-dlp`, `av`, `numpy` and a speech-to-text engine (see [audio-setup.md](audio-setup.md)). The default is `$YT_LECTURE_AUDIO_PYTHON`, or the server's own Python. It can be set only here, never by a tool call, so a client cannot make the server run another program.

## Add it to your agents

Most MCP clients take a stdio server as a command plus arguments in their MCP settings:

```json
{
  "mcpServers": {
    "yt-lecture": {
      "command": "python",
      "args": ["/absolute/path/to/yt-lecture-overview/scripts/yt_lecture_mcp.py", "--out", "/absolute/path/to/notes",
               "--audio-python", "/absolute/path/to/.yt-audio/bin/python"]
    }
  }
}
```

From a skill-hub clone, `tools/install.py` can write that entry into every detected agent's config for you, with backups:

```bash
python tools/install.py --add-mcp yt-lecture --mcp-command "python /absolute/path/to/yt-lecture-overview/scripts/yt_lecture_mcp.py --out /absolute/path/to/notes --audio-python /absolute/path/to/.yt-audio/bin/python" --mcp-test
python tools/install.py --remove-mcp yt-lecture        # to take it out again
```

On Windows, use `py` or the full path to `python.exe` if `python` is not on the PATH that the agent sees.

## Test it

```bash
# protocol smoke test plus a tool call (uses the mcp-server-builder skill's probe)
python <mcp-server-builder>/scripts/mcp_probe.py --call yt_check_video --args '{"url": "https://youtu.be/<id>"}' -- python scripts/yt_lecture_mcp.py

# offline unit tests (also cover the server)
python -m unittest discover -s scripts -p "test_*.py" -v
```

## Notes

- Only `www.youtube.com`, `youtube.com`, `m.youtube.com` and `i.ytimg.com` are contacted. The scripts refuse any other URL.
- The audio stage runs `yt-dlp` and a speech-to-text model on the machine that runs the server. A one-hour lecture can take several minutes on a CPU, so give the client a long tool timeout, or pass `clip` or `source: "captions"`.
- Logs go to stderr. stdout carries protocol messages only.
