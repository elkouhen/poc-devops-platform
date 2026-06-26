from __future__ import annotations

import sys


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)
