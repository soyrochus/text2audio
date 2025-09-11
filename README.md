# text2audio — Text/Markdown → Spoken Audio

A modular CLI utility that converts a text or Markdown file into a narrated audio file using OpenAI TTS.
The tool optionally translates text and streams the synthesized audio directly to disk to avoid large memory buffers.

This README explains how the package works, all available parameters, environment variables, and provides copy-paste examples.



## Quick summary: What is text2audio?

- [Read the overview narration](examples/description-text2audio.md)
- [Listen to the output in English](examples/description-text2audio-en.mp3)
- [Listen to the output in Spanish](examples/description-text2audio-es.mp3)

- [See rhythm & stress demo](examples/control-rhythm-text2audio.md)
- [Listen to the resulting effect](examples/control-rhythm-text2audio-en.mp3)

```
Text2audio is a tool that lets your text become voice.  
You write your narration in a file, and the script takes care of the rest.  

First, it reads your words.  
Then, if you want, it translates them into another language.  
It uses one of the latest GPT models, so the translation sounds fluent and natural.  

Finally, text2audio passes everything to OpenAI’s speech models.  
They generate clear, realistic voices.  
You choose the style, the format, and the output file.  

In the end, you get a ready-to-use audio track.  
It can be in English, Spanish, or any supported language.  
It can be MP3, WAV, AAC, or Opus.  

That’s the idea: write once, speak anywhere, with text2audio.
```

## Package Structure

text2audio is now organized as a modular Python package:

- `text2audio/model.py`: Model selection and audio generation functionality
- `text2audio/ui.py`: User interface, progress bars, and audio playback
- `text2audio/cli.py`: Command-line parsing and application initialization  
- `text2audio/__main__.py`: Package entry point for `python -m text2audio`

## Installation (using uv)

This project uses `uv` to manage the virtual environment and dependencies.

* Get `uv`: [visit the `uv` project page for your platform and installation instructions](https://docs.astral.sh/uv/).


* Create the venv and install declared dependencies:

  ```bash
  uv sync
  ```

## What the package does (high level)

1. Parse CLI arguments.
2. Read and sanitize the input Markdown/text (removes code fences, links, images, formatting).
3. Optionally translate the text to the requested target language using an OpenAI text model.
4. Pass the text to the OpenAI TTS API with optional voice instructions and speed control, which streams audio directly to the output file.

## Shaping Speech with Text

OpenAI TTS does **not** support SSML or custom markup.
You can still guide rhythm and emphasis using normal punctuation:

* **Periods (`.`)** → medium pauses.
* **Ellipses (`…`)** → longer, softer pauses.
* **Commas (`,`)** → short pauses inside a sentence.
* **Dashes (`—`)** → marked breaks with tonal shift.
* **Isolated words / short sentences** → natural stress.
* **Paragraph breaks** → strong pauses between sections.

See [examples/control-rhythm-text2audio.md](examples/control-rhythm-text2audio.md) for a practical demo.

## Voice Control Features

### Speech Speed
Use the `--speed` parameter to control the rate of speech:
* Range: 0.25 to 4.0
* Default: 1.0 (normal speed)
* Examples: `--speed 0.5` (half speed), `--speed 1.5` (1.5x speed)

### Voice Instructions  
Use the `--instructions` parameter to provide additional guidance for voice generation:
* Only works with `gpt-4o-mini-tts` model
* Ignored for `tts-1` and `tts-1-hd` models
* Examples: `--instructions "Speak in a calm, professional tone"` or `--instructions "Use a cheerful, energetic voice"`

## CLI parameters

* `--prompt-file <path>` (required): Path to the input text or Markdown file.
* `--audio-file <path>` (required): Path for the output audio file (e.g. `voice.mp3`).
* `--audio-format <mp3|wav|opus|aac>` (default: `mp3`): Output audio format.
* `--language <language>` (required): Target spoken language (e.g. `english`, `spanish`).
* `--voice <voice-name>` (default: `alloy` or `OPENAI_TTS_VOICE`): TTS voice name.
* `--tts-model <model>` (default: `tts-1-hd` or `OPENAI_TTS_MODEL`): TTS model (`tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`).
* `--text-model <model>` (default: `gpt-5-mini` or `OPENAI_TEXT_MODEL`): Text model for translation.
* `--speed <value>` (default: `1.0`): Speech speed from 0.25 to 4.0.
* `--instructions <text>`: Additional voice instructions for speech generation (ignored for `tts-1`/`tts-1-hd` models).
* `--no-translate`: Skip translation even if target language differs.
* `--list-voices`: Print the built-in list of common voices and exit.
* `--probe-voices`: Generate 1-second test clips for known voices to discover which are available.
* `--play-audio`: After saving the file, play it locally (macOS/Linux only).

## Progress & playback feedback

The CLI shows a Rich-based progress indicator for the main stages:

- Load/clean text
- Optional translation
- Audio synthesis (streaming)

When you pass `--probe-voices`, a Rich progress bar tracks per-voice test generation.

If you add `--play-audio`, the app plays the generated file and shows a small animated
indicator while playback is active. Playback support is implemented for macOS and Linux only.
Windows support may be implemented at a later date.

## Environment variables

* `OPENAI_API_KEY` (required): Your OpenAI API key.
* `OPENAI_TEXT_MODEL` (optional): Override the default text model.
* `OPENAI_TTS_MODEL` (optional): Override the default TTS model.
* `OPENAI_TTS_VOICE` (optional): Override the default voice.



## Usage

The package can be run as a module:

```bash
python -m text2audio [options]
```

Or imported and used programmatically:

```python
import text2audio
text2audio.main()  # equivalent to CLI
```

## Examples (using uv)

1. **English MP3 narration**

```bash
uv add voice:en -- python -m text2audio \
  --prompt-file examples/description-text2audio.md \
  --audio-file examples/description-text2audio.mp3 \
  --audio-format mp3 \
  --language english \
  --voice alloy \
  --tts-model tts-1-hd

uv run voice:en
```

2. **Spanish WAV narration (auto-translation) with custom speed**

```bash
uv add voice:es -- python -m text2audio \
  --prompt-file examples/description-text2audio.md \
  --audio-file examples/description-text2audio-es.wav \
  --audio-format wav \
  --language spanish \
  --voice verse \
  --tts-model gpt-4o-mini-tts \
  --speed 0.9

uv run voice:es
```

3. **Narration with voice instructions (gpt-4o-mini-tts only)**

```bash
uv add voice:custom -- python -m text2audio \
  --prompt-file examples/description-text2audio.md \
  --audio-file examples/description-custom.mp3 \
  --audio-format mp3 \
  --language english \
  --voice alloy \
  --tts-model gpt-4o-mini-tts \
  --instructions "Speak in a calm, professional tone with clear pronunciation"

uv run voice:custom
```

4. **Disable translation (speak original text as-is)**

```bash
uv add voice:raw -- python -m text2audio \
  --prompt-file examples/description-text2audio.md \
  --audio-file examples/voice_raw.mp3 \
  --audio-format mp3 \
  --language english \
  --no-translate

uv run voice:raw
```

5. **List known voices**

```bash
uv add list:voices -- python -m text2audio --list-voices
uv run list:voices
```

6. **Probe which voices work on your account**

```bash
uv add probe:voices -- python -m text2audio --probe-voices --audio-format mp3 --tts-model tts-1-hd
uv run probe:voices
```

7. **Generate and play the output locally (macOS/Linux)**

```bash
uv add voice:play -- python -m text2audio \
  --prompt-file examples/description-text2audio.md \
  --audio-file examples/description-text2audio.mp3 \
  --audio-format mp3 \
  --language english \
  --voice alloy \
  --tts-model tts-1-hd \
  --play-audio

uv run voice:play
```

## Troubleshooting

* **Missing `OPENAI_API_KEY`** → set it in your environment or `.env`.
* **Audio generation fails** → check API error (network, quota, or invalid model/voice).
* **Voice rejected** → try another from `--list-voices` or `--probe-voices`.
* **No sound when using `--play-audio`** → Ensure a local player is installed.
  - macOS: uses the built-in `afplay` (no install needed). Fallbacks: `ffplay`, `mpv`, `vlc`.
  - Linux: tries `ffplay` (FFmpeg), then `mpv`, `vlc`, `mplayer`, or format-specific tools like `mpg123` (MP3) or `aplay` (WAV). Install one of these if missing.

## Security & cost

* Translation and TTS consume tokens; monitor your OpenAI usage.
* Do not commit `.env` with your API key.

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss your idea.


## License

MIT License. See [LICENSE](LICENSE.txt).
© 2025 Iwan van der Kleijn
