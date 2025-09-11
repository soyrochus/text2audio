#!/usr/bin/env python3
"""
Legacy compatibility script for text2audio.

This script provides backward compatibility for users who might still
call the original text2audio.py script directly. It simply imports
and calls the new modular implementation.
"""

from text2audio.cli import main

if __name__ == "__main__":
    main()