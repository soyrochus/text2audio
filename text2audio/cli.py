"""
CLI module for text2audio package.

Contains command-line argument parsing and main application logic.
"""

import argparse
import os
import sys
from pathlib import Path
import regex as re
from dotenv import load_dotenv
from openai import OpenAI

from .model import KNOWN_VOICES, KNOWN_TTS_MODELS, FORMAT_MAP, synthesize_tts, probe_voices
from .ui import progress_context, play_audio_file


# ----------------------------
# Language handling
# ----------------------------
LANG_ALIASES = {
    "en": "english", "eng": "english",
    "es": "spanish", "spa": "spanish", "castellano": "spanish",
}


def norm_language(lang: str) -> str:
    """Normalize language name using aliases."""
    lang = (lang or "").strip().lower()
    return LANG_ALIASES.get(lang, lang)


# ----------------------------
# Text processing
# ----------------------------
def load_text_strip_markdown(path: Path) -> str:
    """Load text file and strip Markdown formatting."""
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
# Translation
# ----------------------------
def detect_language_hint(text: str) -> str:
    """Detect language based on character markers."""
    spanish_markers = re.findall(r"[áéíóúñ¡¿]", text.lower())
    return "spanish" if len(spanish_markers) >= 2 else "english"


def translate_if_needed(client: OpenAI, text: str, target_language: str, text_model: str) -> str:
    """Translate text if needed based on target language."""
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
# CLI setup
# ----------------------------
def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
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

    # New parameters
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Speech speed (0.25-4.0, default: 1.0).")
    parser.add_argument("--instructions", 
                        help="Additional voice instructions (ignored for tts-1/tts-1-hd models).")

    parser.add_argument("--no-translate", action="store_true",
                        help="Do not translate even if target language differs.")

    parser.add_argument("--list-voices", action="store_true",
                        help="Print a curated list of common voice names and exit.")
    parser.add_argument("--probe-voices", action="store_true",
                        help="Synthesize a 1-second sample per known voice to discover availability.")
    parser.add_argument("--play-audio", action="store_true",
                        help="Play the saved audio after synthesis (macOS/Linux only).")

    return parser


def validate_args(args) -> None:
    """Validate command-line arguments."""
    # Validate speed parameter
    if not (0.25 <= args.speed <= 4.0):
        raise ValueError(f"Speed must be between 0.25 and 4.0, got {args.speed}")


# ----------------------------
# Main application logic
# ----------------------------
def main():
    """Main entry point for the text2audio CLI application."""
    load_dotenv()
    
    parser = create_parser()
    args = parser.parse_args()
    
    # Validate arguments
    try:
        validate_args(args)
    except ValueError as e:
        parser.error(str(e))

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
    with progress_context() as progress:
        # 1) Load text
        if progress:
            t_load = progress.add_task("Loading and cleaning text...", total=None)
        else:
            print("Loading and cleaning text...")
        raw_text = load_text_strip_markdown(prompt_path)
        if progress:
            progress.stop_task(t_load)

        # 2) Translate if needed
        target_lang = norm_language(args.language)
        text_for_tts = raw_text
        if not args.no_translate:
            if progress:
                t_tr = progress.add_task(f"Translating to {target_lang}...", total=None)
            else:
                print(f"Translating to {target_lang}...")
            text_for_tts = translate_if_needed(client, text_for_tts, target_lang, args.text_model)
            if progress:
                progress.stop_task(t_tr)

        # 3) Synthesize
        if progress:
            t_syn = progress.add_task("Synthesizing audio (streaming)...", total=None)
        else:
            print("Synthesizing audio (streaming)...")
        synthesize_tts(
            client=client,
            text=text_for_tts,
            out_path=out_path,
            audio_format=args.audio_format,
            tts_model=args.tts_model,
            voice=args.voice,
            speed=args.speed,
            instructions=args.instructions,
        )
        if progress:
            progress.stop_task(t_syn)

    print(f"Saved narration to: {out_path}")
    if args.play_audio:
        play_audio_file(out_path)