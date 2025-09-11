"""
Entry point for the text2audio package when run as a module.

This allows the package to be executed directly with:
    python -m text2audio
"""

from .cli import main

if __name__ == "__main__":
    main()