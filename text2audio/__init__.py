"""
text2audio - Text/Markdown to spoken audio conversion using OpenAI TTS.

A modular CLI utility that converts text or Markdown files into narrated audio
files using OpenAI's text-to-speech API with optional translation capabilities.
"""

__version__ = "0.1.0"
__author__ = "Iwan van der Kleijn"

from .model import synthesize_tts, probe_voices
from .ui import play_audio_file
from .cli import main

__all__ = ["synthesize_tts", "probe_voices", "play_audio_file", "main"]