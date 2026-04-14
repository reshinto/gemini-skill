#!/usr/bin/env python
"""Health check for the gemini-skill.

2.7-safe launcher.
"""
import os
import sys

if sys.version_info < (3, 9):
    sys.exit(
        "gemini-skill requires Python 3.9+. Found: {}.{}".format(
            sys.version_info[0], sys.version_info[1]
        )
    )

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cli.health_main import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1:])
