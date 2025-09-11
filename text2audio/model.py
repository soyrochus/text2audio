"""
Model module for text2audio package.

Contains model selection, audio generation, and voice management functionality.
"""

import tempfile
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI

# ----------------------------
# Constants and catalogs
# ----------------------------
KNOWN_VOICES = [
    "alloy", "verse", "coral", "onyx", "shimmer",
    "fable", "echo", "nova", "sage", "ash", "ballad",
]

KNOWN_TTS_MODELS = ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]

FORMAT_MAP = {"mp3": "mp3", "wav": "wav", "opus": "opus", "aac": "aac"}


# ----------------------------
# Audio synthesis
# ----------------------------
def synthesize_tts(
    client: OpenAI, 
    text: str, 
    out_path: Path, 
    audio_format: str, 
    tts_model: str, 
    voice: str,
    speed: float = 1.0,
    instructions: str = None
):
    """
    Synthesize text to speech using OpenAI TTS API.
    
    Args:
        client: OpenAI client instance
        text: Text to synthesize
        out_path: Output file path
        audio_format: Audio format (mp3, wav, opus, aac)
        tts_model: TTS model to use
        voice: Voice name
        speed: Speech speed (0.25-4.0, default 1.0)
        instructions: Voice instructions (ignored for tts-1/tts-1-hd)
    """
    fmt = FORMAT_MAP[audio_format]
    
    # Prepare TTS parameters
    tts_params = {
        "model": tts_model,
        "voice": voice,
        "input": text,
        "response_format": fmt,
        "speed": speed,
    }
    
    # Add instructions only for models that support it (not tts-1 or tts-1-hd)
    if instructions and tts_model not in ["tts-1", "tts-1-hd"]:
        tts_params["instructions"] = instructions
    
    # Current SDK uses 'response_format' (not 'format')
    with client.audio.speech.with_streaming_response.create(**tts_params) as response:
        response.stream_to_file(out_path)


def probe_voices(client: OpenAI, voices: List[str], tts_model: str, audio_format: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Synthesize a short sample per voice to discover which are available for this account.
    
    Args:
        client: OpenAI client instance
        voices: List of voice names to test
        tts_model: TTS model to use for testing
        audio_format: Audio format for test samples
        
    Returns:
        Tuple of (successful_voices, failed_voices_with_errors)
    """
    from .ui import progress_context  # Import here to avoid circular imports
    
    tmpdir = Path(tempfile.mkdtemp(prefix="tts_voices_"))
    print(f"Probing voices into: {tmpdir}")
    ok, bad = [], []
    sample_text = "Testing voice sample."
    
    with progress_context("Synthesizing voice samples...", total=len(voices)) as progress:
        task = progress.add_task("Synthesizing voice samples...", total=len(voices)) if progress else None
        for v in voices:
            out = tmpdir / f"{v}.{audio_format}"
            try:
                synthesize_tts(client, sample_text, out, audio_format, tts_model, v)
                ok.append(v)
            except Exception as e:
                bad.append((v, str(e)))
            finally:
                if progress and task:
                    progress.advance(task, 1)
    
    print("\nAvailable voices (succeeded):")
    for v in ok:
        print(f"  - {v}")
    if bad:
        print("\nFailed voices (diagnostic):")
        for v, err in bad:
            print(f"  - {v}: {err}")
    return ok, bad