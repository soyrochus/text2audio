# text2audio — Text/Markdown → Spoken Audio

A small CLI utility that converts a text or Markdown file into a narrated audio file using OpenAI TTS. The tool optionally translates text, applies simple prosody markup, shapes cadence for better narration, and streams the synthesized audio to disk to avoid large memory buffers.

This README explains how the script works, all available parameters, the prosody/MPM concepts, environment variables, and provides copy-paste examples that use `uv add` / `uv run` (see notes about `uv` below).

## Quick summary

- Input: a text or Markdown file (e.g., `script.md`).
- Output: an audio file (mp3/wav/opus/aac).
- Main features: Markdown stripping, optional translation (via OpenAI), Minimal Prosody Markup (MPM), cadence induction, streaming TTS synthesis.

## Installation (minimal)

This project requires Python 3.8+ and these packages:

- openai (OpenAI SDK)
- regex (the `regex` package; used as a drop-in replacement for `re` with nicer features)
- python-dotenv (optional; loads `.env` variables)

Install them with pip:

```bash
python -m pip install --upgrade pip
python -m pip install openai regex python-dotenv
```

Create a `.env` in the project root or export `OPENAI_API_KEY` in your shell:

```text
OPENAI_API_KEY=sk-...
```

If you want to override model/voice defaults you can also set:

```text
OPENAI_TEXT_MODEL=gpt-5-mini
OPENAI_TTS_MODEL=tts-1-hd
OPENAI_TTS_VOICE=alloy
```

## What the script does (high level)

1. Parse CLI arguments.
2. Read and sanitize the input Markdown/text (removes code fences, links, images, headings formatting, etc.).
3. Optionally translate the text to the requested target language using an OpenAI text model.
4. Optionally apply Minimal Prosody Markup (MPM) tags that are converted into punctuation/spacing. This helps influence how the TTS engine speaks.
5. Optionally induce simple prosody/cadence changes (like turning blank lines into longer pauses).
6. Call the OpenAI TTS streaming API and write the audio directly to the output file.

## Important concepts

Prosody
- Prosody refers to rhythm, stress, and intonation in speech. Small punctuation and spacing cues (commas, ellipses, dashes, paragraph breaks) significantly influence how a TTS engine reads text aloud.

Minimal Prosody Markup (MPM)
- MPM is a tiny, human-friendly markup supported by the script to express prosodic intents without using SSML. Supported tags:
  - `[[pause:s|m|l]]` or `[[pause:200ms]]` — short/medium/long or explicit ms pause.
  - `[emph]...[/emph]` — emphasize a phrase (converted to dashes or other punctuation to make the TTS emphasize it).
  - `[spell]WORD[/spell]` — expand into spelled-out characters (useful for acronyms or codes).

These tags are replaced with punctuation and spacing that the TTS model tends to react to (commas, ellipses, sentence breaks).

Cadence shaping / Induced prosody
- The script has a simple function that maps paragraph or line breaks to sentence-ending punctuation so the voice pauses naturally at paragraph boundaries.

Translation behavior
- The script will auto-detect a light language hint (very simple heuristic) and will call a text-model to translate to the requested target language unless `--no-translate` is set. The translator is instructed to preserve line breaks and sentence boundaries to keep narration-friendly structure.

Streaming synthesis
- Audio is streamed to disk while being generated to avoid keeping the whole audio in memory.

## CLI parameters (full list)

- `--prompt-file <path>` (required): Path to the input text or Markdown file containing the narration script.
- `--audio-file <path>` (required): Path for the output audio file (e.g., `voice.mp3`). Parent directories will be created if necessary.
- `--audio-format <mp3|wav|opus|aac>` (default: `mp3`): Output audio format. The script maps these names directly to the TTS API format.
- `--language <language>` (required): Target spoken language (for example `english`, `spanish`). The script normalizes common aliases like `en`/`eng` -> `english`, `es`/`spa` -> `spanish`.
- `--voice <voice-name>` (default: `alloy` or `OPENAI_TTS_VOICE` env var): The TTS voice name to request. The script contains a short `KNOWN_VOICES` list but you can pass any voice string supported by the API.
- `--tts-model <model>` (default: `tts-1-hd` or `OPENAI_TTS_MODEL` env var): The TTS model to use. Known options in-script are `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`.
- `--text-model <model>` (default: `gpt-5-mini` or `OPENAI_TEXT_MODEL` env var): Text model used for optional translation/normalization.
- `--no-translate` (flag): Skip translation even if the target language differs from the detected source.
- `--no-prosody` (flag): Disable automatic cadence shaping (the `induce_prosody` step).
- `--no-mpm` (flag): Do not process Minimal Prosody Markup tags; leave them untouched in the final text.
- `--list-voices` (flag): Print the in-script `KNOWN_VOICES` list and exit.

Environment variables

- `OPENAI_API_KEY` (required): Your OpenAI API key. The script exits if this is not present.
- `OPENAI_TEXT_MODEL` (optional): Overrides the default text model.
- `OPENAI_TTS_MODEL` (optional): Overrides the default TTS model.
- `OPENAI_TTS_VOICE` (optional): Overrides the default voice.

Exit codes and errors

- Exit code `2` — prompt file not found.
- Exit code `3` — missing `OPENAI_API_KEY`.
- Network/API errors may raise exceptions (the translator tries Responses API first, then falls back to chat completions if the Responses call fails).

## Examples (using `uv add` / `uv run`)

Note: You asked for examples using `uv add` and `uv run`. This README assumes you have a simple `uv` task runner that supports adding named commands with `uv add <name> -- <command...>` and executing them with `uv run <name>`. If your `uv` behaves differently, adapt these lines to your environment.

1) Basic English MP3 narration

```bash
uv add voice:en -- python text2audio.py \
  --prompt-file examples/reagent.txt \
  --audio-file outputs/voice_en.mp3 \
  --audio-format mp3 \
  --language english \
  --voice alloy \
  --tts-model tts-1-hd

uv run voice:en
```

2) Spanish WAV narration with a different voice (auto-translation enabled)

```bash
uv add voice:es -- python text2audio.py \
  --prompt-file examples/reagent.txt \
  --audio-file outputs/voz_es.wav \
  --audio-format wav \
  --language spanish \
  --voice verse \
  --tts-model gpt-4o-mini-tts

uv run voice:es
```

3) Disable translation (speak original text even if language differs)

```bash
uv add voice:raw -- python text2audio.py \
  --prompt-file examples/text2audo.txt \
  --audio-file outputs/voice_raw.mp3 \
  --audio-format mp3 \
  --language english \
  --no-translate

uv run voice:raw
```

4) Disable MPM and prosody shaping (raw, literal read)

```bash
uv add voice:literal -- python text2audio.py \
  --prompt-file examples/reagent.txt \
  --audio-file outputs/voice_literal.mp3 \
  --audio-format mp3 \
  --language english \
  --no-mpm \
  --no-prosody

uv run voice:literal
```

5) List known voices

```bash
uv add list:voices -- python text2audio.py --list-voices
uv run list:voices
```

## Markdown and MPM examples

Given a small `script.md` like:

```markdown
# Episode Intro

Welcome to the show. [[pause:m]] Today we talk about technology.

[emph]Important:[/emph] Backup your data.

[spell]AI[/spell] stands for artificial intelligence.
```

After Markdown stripping and MPM processing the assistant will produce a narration-friendly text similar to:

"Episode Intro

Welcome to the show … Today we talk about technology. — Important: — Backup your data. A I stands for artificial intelligence."

This text includes punctuation and spacing that improve the spoken cadence.

## Tips for better results

- Shorter, clear sentences work best for narration.
- Use `[[pause:m]]` or paragraph breaks to indicate longer pauses between ideas.
- Use `[emph]...[/emph]` sparingly for emphasis.
- Use `[spell]...[/spell]` for acronyms or codes that should be spelled out.
- Review translations before generating final long audio runs; automatic detection/translation is conservative.

## Troubleshooting

- If you see "Missing OPENAI_API_KEY" — set the `OPENAI_API_KEY` env var or create a `.env` file.
- If audio fails to generate, inspect the API error (network, quota, or invalid model/voice name).
- If your TTS model rejects a voice name, try another voice from the printed `--list-voices` output or consult your API provider's voice catalog.

## Security & cost

- API usage for translation and TTS may incur costs. Monitor your account.
- Do not commit `OPENAI_API_KEY` to source control.

## Where to go next

- Add unit tests around `load_text_strip_markdown`, `apply_mpm`, and `induce_prosody` if you plan to change parsing logic.
- Consider adding SSML support if you need more precise control than punctuation-based MPM.

---

If you want, I can also:

- Add a `requirements.txt` or update `pyproject.toml` with the explicit dependencies.
- Create a small `uv` configuration file (if you describe the exact `uv` tool you use) so `uv add` commands run out of the box.
