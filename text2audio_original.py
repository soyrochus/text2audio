#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path
import tempfile
import shutil
import subprocess
import time
import regex as re
from dotenv import load_dotenv

# Optional Rich progress UI
HAS_RICH = True
try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn
    from rich.console import Console
except Exception:
    HAS_RICH = False
    Console = None

try:
    from openai import OpenAI
except ImportError:
    print("Please install the OpenAI SDK:  pip install openai", file=sys.stderr)
    sys.exit(1)

# ----------------------------
# Simple catalogs / defaults
# ----------------------------
KNOWN_VOICES = [
    "alloy", "verse", "coral", "onyx", "shimmer",
    "fable", "echo", "nova", "sage", "ash", "ballad",
]

KNOWN_TTS_MODELS = ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]

FORMAT_MAP = {"mp3": "mp3", "wav": "wav", "opus": "opus", "aac": "aac"}

LANG_ALIASES = {
    "en": "english", "eng": "english",
    "es": "spanish", "spa": "spanish", "castellano": "spanish",
}

def norm_language(lang: str) -> str:
    lang = (lang or "").strip().lower()
    return LANG_ALIASES.get(lang, lang)

# ----------------------------
# Markdown → plain text
# ----------------------------
def load_text_strip_markdown(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    txt = re.sub(r"```.*?```", "", raw, flags=re.DOTALL)
    txt = re.sub(r"`([^`]*)`", r"\1", txt)
    txt = re.sub(r"!\[.*?\]\(.*?\)", "", txt)
    txt = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", txt)
    txt = re.sub(r"^\s{0,3}#{1,6}\s*", "", txt, flags=re.MULTILINE)
    txt = re.sub(r"^\s{0,3}[-*+]\s+", "", txt, flags=re.MULTILINE)
    txt = re.sub(r"^\s{0,3}\d+\.\s+", "", txt, flags=re.MULTILINE)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    return txt.strip()

# ----------------------------
# Very light language hint + translation
# ----------------------------
def detect_language_hint(text: str) -> str:
    spanish_markers = re.findall(r"[áéíóúñ¡¿]", text.lower())
    return "spanish" if len(spanish_markers) >= 2 else "english"

def translate_if_needed(client, text: str, target_language: str, text_model: str) -> str:
    target_language = norm_language(target_language)
    src_hint = detect_language_hint(text)
    if src_hint == target_language:
        return text

    system_prompt = (
        "You are a professional narrator's translator. "
        "Translate faithfully into the target language for voice narration. "
        "Preserve line breaks and sentence boundaries. No explanations."
    )
    user_prompt = f"Target language: {target_language}\n\nText:\n{text}"

    # Prefer Responses API; fall back to chat.completions if needed.
    try:
        resp = client.responses.create(
            model=text_model,
            input=[{"role": "system", "content": system_prompt},
                   {"role": "user", "content": user_prompt}],
        )
        return resp.output_text.strip()
    except Exception:
        chat = client.chat.completions.create(
            model=text_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return chat.choices[0].message.content.strip()

# ----------------------------
# Synthesis
# ----------------------------
def synthesize_tts(client, text: str, out_path: Path, audio_format: str, tts_model: str, voice: str):
    fmt = FORMAT_MAP[audio_format]
    # Current SDK uses 'response_format' (not 'format')
    with client.audio.speech.with_streaming_response.create(
        model=tts_model,
        voice=voice,
        input=text,
        response_format=fmt,
    ) as response:
        response.stream_to_file(out_path)

def _select_player_cmd(audio_path: Path):
    """Return a list suitable for subprocess to play audio on macOS/Linux, or None if not found."""
    ext = audio_path.suffix.lower().lstrip(".")
    platform = sys.platform
    # macOS: afplay is standard
    if platform == "darwin":
        if shutil.which("afplay"):
            return ["afplay", str(audio_path)]
        # Fallbacks on mac if present
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)]
        if shutil.which("mpv"):
            return ["mpv", "--no-video", "--really-quiet", str(audio_path)]
        if shutil.which("vlc"):
            return ["vlc", "--intf", "dummy", "--play-and-exit", "--quiet", str(audio_path)]
        return None
    # Linux
    if platform.startswith("linux"):
        # Prefer ffplay/mpv/vlc/mplayer
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)]
        if shutil.which("mpv"):
            return ["mpv", "--no-video", "--really-quiet", str(audio_path)]
        if shutil.which("vlc"):
            return ["vlc", "--intf", "dummy", "--play-and-exit", "--quiet", str(audio_path)]
        if shutil.which("mplayer"):
            return ["mplayer", "-really-quiet", str(audio_path)]
        # Format-specific fallbacks
        if ext in {"mp3", "aac", "opus"} and shutil.which("mpg123"):
            return ["mpg123", "-q", str(audio_path)]
        if ext in {"wav"} and shutil.which("aplay"):
            return ["aplay", str(audio_path)]
        if shutil.which("paplay"):
            return ["paplay", str(audio_path)]
        if shutil.which("play"):
            return ["play", "-q", str(audio_path)]
        return None
    # Ignore Windows per requirements
    return None

def play_audio_file(audio_path: Path):
    cmd = _select_player_cmd(audio_path)
    if not cmd:
        print("No suitable audio player found for your OS/path. Skipping playback.")
        return 1
    if HAS_RICH:
        console = Console()
        eq_frames = [
            "▁▂▃▄▅▆▇▆▅▄▃▂",
            "▂▃▄▅▆▇▆▅▄▃▂▁",
            "▃▄▅▆▇▆▅▄▃▂▁▂",
            "▄▅▆▇▆▅▄▃▂▁▂▃",
            "▅▆▇▆▅▄▃▂▁▂▃▄",
            "▆▇▆▅▄▃▂▁▂▃▄▅",
            "▇▆▅▄▃▂▁▂▃▄▅▆",
            "▆▅▄▃▂▁▂▃▄▅▆▇",
            "▅▄▃▂▁▂▃▄▅▆▇▆",
            "▄▃▂▁▂▃▄▅▆▇▆▅",
            "▃▂▁▂▃▄▅▆▇▆▅▄",
            "▂▁▂▃▄▅▆▇▆▅▄▃",
        ]
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Playing audio…", total=None)
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            i = 0
            while proc.poll() is None:
                frame = eq_frames[i % len(eq_frames)]
                progress.update(task, description=f"Playing audio {frame}")
                time.sleep(0.15)
                i += 1
            progress.stop_task(task)
        return proc.returncode or 0
    else:
        print("Playing audio…")
        try:
            return subprocess.call(cmd)
        finally:
            print("Playback finished.")

def probe_voices(client, voices, tts_model, audio_format):
    """Synthesize a short sample per voice to discover which are live for this account."""
    tmpdir = Path(tempfile.mkdtemp(prefix="tts_voices_"))
    print(f"Probing voices into: {tmpdir}")
    ok, bad = [], []
    sample_text = "Testing voice sample."
    if HAS_RICH:
        console = Console()
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Synthesizing voice samples...", total=len(voices))
            for v in voices:
                out = tmpdir / f"{v}.{audio_format}"
                try:
                    synthesize_tts(client, sample_text, out, audio_format, tts_model, v)
                    ok.append(v)
                except Exception as e:
                    bad.append((v, str(e)))
                finally:
                    progress.advance(task, 1)
    else:
        for v in voices:
            out = tmpdir / f"{v}.{audio_format}"
            try:
                synthesize_tts(client, sample_text, out, audio_format, tts_model, v)
                ok.append(v)
            except Exception as e:
                bad.append((v, str(e)))
    print("\nAvailable voices (succeeded):")
    for v in ok:
        print(f"  - {v}")
    if bad:
        print("\nFailed voices (diagnostic):")
        for v, err in bad:
            print(f"  - {v}: {err}")
    return ok, bad

# ----------------------------
# CLI
# ----------------------------
def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="text2audio",
        description="Generate a narrated voice track from text/Markdown using OpenAI TTS."
    )
    parser.add_argument("--prompt-file", help="Text/Markdown file with the narration.")
    parser.add_argument("--audio-file", help="Output audio file path (e.g., voice.mp3).")
    parser.add_argument("--audio-format", default="mp3", choices=list(FORMAT_MAP.keys()),
                        help="Audio format (mp3|wav|opus|aac).")
    parser.add_argument("--language", help="Target spoken language (e.g., 'english', 'spanish').")

    parser.add_argument("--voice", default=os.getenv("OPENAI_TTS_VOICE", "alloy"),
                        help="TTS voice name (e.g., alloy, verse, ...).")
    parser.add_argument("--tts-model", default=os.getenv("OPENAI_TTS_MODEL", "tts-1-hd"),
                        choices=KNOWN_TTS_MODELS, help="TTS model.")
    parser.add_argument("--text-model", default=os.getenv("OPENAI_TEXT_MODEL", "gpt-5-mini"),
                        help="Text model for translation/normalization (e.g., gpt-5, gpt-5-mini).")

    parser.add_argument("--no-translate", action="store_true",
                        help="Do not translate even if target language differs.")

    parser.add_argument("--list-voices", action="store_true",
                        help="Print a curated list of common voice names and exit.")
    parser.add_argument("--probe-voices", action="store_true",
                        help="Synthesize a 1-second sample per known voice to discover availability.")
    parser.add_argument("--play-audio", action="store_true",
                        help="Play the saved audio after synthesis (macOS/Linux only).")

    args = parser.parse_args()

    # Handle meta commands immediately
    if args.list_voices:
        print("Known voice names (availability may vary by account):")
        for v in KNOWN_VOICES:
            print(f" - {v}")
        sys.exit(0)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Missing OPENAI_API_KEY (set it in your environment or .env).", file=sys.stderr)
        sys.exit(3)

    client = OpenAI(api_key=api_key)

    if args.probe_voices:
        probe_voices(client, KNOWN_VOICES, args.tts_model, args.audio_format)
        sys.exit(0)

    # For normal narration mode, require these
    if not args.prompt_file or not args.audio_file or not args.language:
        parser.error("--prompt-file, --audio-file, and --language are required unless using --list-voices or --probe-voices")


    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        print(f"Prompt file not found: {prompt_path}", file=sys.stderr)
        sys.exit(2)

    out_path = Path(args.audio_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Progress-assisted workflow
    if HAS_RICH:
        console = Console()
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            transient=True,
            console=console,
        ) as progress:
            # 1) Load text
            t_load = progress.add_task("Loading and cleaning text...", total=None)
            raw_text = load_text_strip_markdown(prompt_path)
            progress.stop_task(t_load)

            # 2) Translate if needed
            target_lang = norm_language(args.language)
            text_for_tts = raw_text
            if not args.no_translate:
                t_tr = progress.add_task(f"Translating to {target_lang}...", total=None)
                text_for_tts = translate_if_needed(client, text_for_tts, target_lang, args.text_model)
                progress.stop_task(t_tr)

            # 3) Synthesize
            t_syn = progress.add_task("Synthesizing audio (streaming)...", total=None)
            synthesize_tts(
                client=client,
                text=text_for_tts,
                out_path=out_path,
                audio_format=args.audio_format,
                tts_model=args.tts_model,
                voice=args.voice,
            )
            progress.stop_task(t_syn)
    else:
        # Fallback to plain mode without Rich
        print("Loading and cleaning text...")
        raw_text = load_text_strip_markdown(prompt_path)

        target_lang = norm_language(args.language)
        text_for_tts = raw_text
        if not args.no_translate:
            print(f"Translating to {target_lang}...")
            text_for_tts = translate_if_needed(client, text_for_tts, target_lang, args.text_model)

        print("Synthesizing audio (streaming)...")
        synthesize_tts(
            client=client,
            text=text_for_tts,
            out_path=out_path,
            audio_format=args.audio_format,
            tts_model=args.tts_model,
            voice=args.voice,
        )

    print(f"Saved narration to: {out_path}")
    if args.play_audio:
        play_audio_file(out_path)

if __name__ == "__main__":
    main()
