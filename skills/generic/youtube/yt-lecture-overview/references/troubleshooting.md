# Troubleshooting and edge cases

| Situation | What happens / what to do |
|---|---|
| Link has `&t=90s`, `?si=…`, `&list=…`, `feature=share` | Ignored. The video id is taken from the link and the canonical `watch?v=` URL is used |
| Playlist link without `v=` | Rejected. Ask for the link of one video from the playlist |
| Shorts | Accepted, but most Shorts titles do not pass the guardrail |
| Live stream still running | The recording is not complete yet. Try again after the stream ends |
| Private, removed, members-only, age- or region-restricted video | Exit 5 from the watch page status. YouTube does not give the audio or captions without a login, so ask the user for a transcript file (`--transcript`) |
| Output says "the text comes from captions" | The audio stage failed (see `warnings`). Run `yt_lecture.py doctor`, install what it lists (or use `--audio-python`), and fetch again. Use `--source audio-only` to make this an error instead |
| `doctor` says an engine "cannot load" | Its native library will not run on this Python or machine. Use another engine (`--engine vosk`) or a separate audio Python; see [audio-setup.md](audio-setup.md). Do not try to get around a security policy |
| yt-dlp warns about a JavaScript runtime, or misses formats | Install Node.js (the script passes `--js-runtimes node`), and keep yt-dlp updated: `pip install -U yt-dlp` |
| Speech-to-text is slow | It already runs greedy decoding and in parallel with the slides. Next, use `--clip 10:00-25:00`, a smaller model (`--model tiny`), `faster-whisper` instead of `openai-whisper`, or `--source captions` when the video has good captions |
| Speech-to-text text has no punctuation (Vosk) | Expected. Write the notes in clean sentences; faster-whisper gives punctuated text |
| Audio analysis looks wrong (music counted as speech, quiet speaker shown as pauses) | The analysis is a loudness estimate. Say so if you use it |
| Lecture is in another language | `--lang hi` (or `es`, `fr`, …, or `auto` with whisper) sets the spoken language for speech-to-text and the caption track for the fallback. Vosk needs a model for that language. Write the notes in the language the user asked for |
| Speech-to-text or captions mishear technical words | Expected. Fix them in `notes.json` from context, and do not repeat the mistakes |
| Very long lecture (2h+) | Read `transcript.txt` in parts. Sections follow the chapters, or ~10-minute parts. Keep one summary for the whole video |
| `slides: 0`: no slides were found | The video has no slides: a talking head only, or a whiteboard drawn by hand with no clean pages. This is normal; the page then has no slide gallery. Write the `hld` from the transcript alone if the lecture describes a system |
| A camera shot, blank frame or end card was kept as a slide | Detection is a measured estimate. Camera shots are skipped when they look soft or keep moving; a sharp, still shot of the room can pass. Set `"hide": true` for that file in `notes.json` and render again |
| A slide that builds up step by step shows up several times | Each step that changes more than ~12% of the screen counts as a new slide. Hide the early steps, or caption them as steps |
| `slides not captured: …` in `warnings` | The text and audio are fine. Usual causes: yt-dlp could not get a video stream, or PyAV cannot decode the codec. Try `--slides-height 480`, update yt-dlp, or use `--no-slides` |
| The video download is too big or slow | Slides use a video-only stream of 720p or less, about 30–45 MB per 10 minutes. Use `--slides-height 480` (about half), `--clip`, or `--no-slides` |
| Many slides (a long talk) | At most 120 are kept: the ones shown longest. The HTML embeds them, so a long talk makes a larger file (about 60 KB per slide) |
| `could not reach YouTube` | Check the network or proxy. `urllib` uses the `HTTPS_PROXY` environment variable |
| YouTube changes its player API and the caption fallback comes back empty | The caption fallback tries `yt-dlp` subtitles next; keep yt-dlp updated |
| A title that should pass is blocked (or the reverse) | The title decides by design. The term lists and weights are at the top of `scripts/yt_guardrail.py`, so add terms there and run the tests. Do not get around the check for one video |
| `render` says the folder was not cleared | The folder's `info.json` has no allowed guardrail verdict. Run `fetch` again on the link |

## How the title score works

- Strong study terms (lecture, tutorial, course, crash course, for beginners, NPTEL, CS50, exam names, system design, systems design, HLD, LLD): +3 each
- Medium (explained, fundamentals, basics, theory, exam, revision, deep dive, lab, high-level design, low-level design): +2 each
- Weak (learn, how to, what is, chapter, part, problem, proof, notes): +1 each
- Subject terms (programming languages, CS, maths, sciences, engineering, economics, history, languages…): +2 each
- Entertainment terms (official video, lyrics, trailer, prank, reaction, gameplay, vlog, drama…): −4 each
- YouTube category Education or Science & Technology, and tags with study terms: +1 each. These count only if the title already has a study or subject term
- **Pass: a score of 3 or more, and at least one study (strong or medium) or subject term in the title**
