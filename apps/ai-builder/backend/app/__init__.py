"""ai-builder backend."""

from pathlib import Path
import sys


def _configure_shared_python_path() -> None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "shared" / "python"
        if candidate.is_dir():
            candidate_text = str(candidate)
            if candidate_text not in sys.path:
                sys.path.insert(0, candidate_text)
            return


_configure_shared_python_path()
