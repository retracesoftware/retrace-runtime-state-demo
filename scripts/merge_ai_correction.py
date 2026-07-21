from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: merge_ai_correction.py INITIAL.json CORRECTED.json OUTPUT.json",
            file=sys.stderr,
        )
        return 2

    initial_path, corrected_path, output_path = map(Path, sys.argv[1:])
    initial = json.loads(initial_path.read_text())
    corrected = json.loads(corrected_path.read_text())
    corrected["transcript"] = [
        *(initial.get("transcript") or []),
        *(corrected.get("transcript") or []),
    ]
    corrected["evidence_correction"] = {
        "performed": True,
        "reason": "Initial summary failed runtime-evidence validation.",
        "initial_debug_session_id": initial.get("debug_session_id"),
        "corrected_debug_session_id": corrected.get("debug_session_id"),
    }
    output_path.write_text(json.dumps(corrected, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
