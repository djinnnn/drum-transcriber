from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def separate_drums(input_audio: str | Path, output_dir: str | Path = "output") -> Path:
    """Run Demucs two-stem separation and return the extracted drums.wav path."""
    input_path = Path(input_audio).expanduser().resolve()
    out_dir = Path(output_dir).expanduser().resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input audio not found: {input_path}")
    demucs_root = out_dir / "demucs"
    cmd = [
        sys.executable,
        "-m",
        "demucs.separate",
        "--two-stems=drums",
        "--name",
        "htdemucs",
        "--out",
        str(demucs_root),
        str(input_path),
    ]
    subprocess.run(cmd, check=True)

    source_name = input_path.stem
    candidate = demucs_root / "htdemucs" / source_name / "drums.wav"
    if not candidate.exists():
        matches = sorted(demucs_root.glob("**/drums.wav"))
        if not matches:
            raise FileNotFoundError("Demucs finished, but no drums.wav was found.")
        candidate = matches[0]

    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / "drums.wav"
    shutil.copy2(candidate, final_path)
    return final_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Separate a mixed audio file into a drums stem with Demucs.")
    parser.add_argument("input_audio")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    print(separate_drums(args.input_audio, args.output_dir))


if __name__ == "__main__":
    main()
