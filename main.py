from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.beat_grid import chart_to_dict, detect_beats, quantize_hits
from pipeline.detect import detect_drums
from pipeline.separate import separate_drums
from pipeline.to_midi import write_midi
from pipeline.to_score import load_sections, render_pdf_with_musescore, write_musicxml


def run_pipeline(
    input_audio: str | Path,
    output_dir: str | Path = "output",
    grid_division: int = 16,
    title: str | None = None,
    composer: str = "",
    creator: str = "",
    sections_json: str | Path | None = None,
    render_pdf: bool = True,
    musescore_path: str | Path | None = None,
) -> dict[str, Path | None]:
    input_path = Path(input_audio).expanduser().resolve()
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    score_title = title or input_path.stem

    drums_wav = separate_drums(input_path, out_dir)
    hits = detect_drums(drums_wav, out_dir / "hits.json")
    bpm, beats = detect_beats(input_path)
    chart = quantize_hits(hits, beats, bpm, grid_division=grid_division)

    quantized_json = out_dir / "quantized.json"
    quantized_json.write_text(json.dumps(chart_to_dict(chart), indent=2), encoding="utf-8")

    midi_path = write_midi(chart, out_dir / "song.mid")
    musicxml_path = write_musicxml(
        chart,
        out_dir / "song.musicxml",
        title=score_title,
        composer=composer,
        creator=creator,
        sections=load_sections(sections_json),
    )
    pdf_path: Path | None = None
    if render_pdf:
        pdf_path = render_pdf_with_musescore(musicxml_path, out_dir / "song.pdf", musescore_path)

    return {
        "drums_wav": drums_wav,
        "hits_json": out_dir / "hits.json",
        "quantized_json": quantized_json,
        "midi": midi_path,
        "musicxml": musicxml_path,
        "pdf": pdf_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command drum transcription pipeline.")
    parser.add_argument("input_audio", help="Input mp3/wav/m4a file")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--grid-division", type=int, default=16)
    parser.add_argument("--title")
    parser.add_argument("--composer", default="")
    parser.add_argument("--creator", default="")
    parser.add_argument("--sections-json", help="JSON object {bar: label} or list of {bar, label} for rehearsal marks.")
    parser.add_argument("--musescore-path")
    parser.add_argument("--no-pdf", action="store_true", help="Only generate MIDI and MusicXML; skip MuseScore PDF rendering.")
    args = parser.parse_args()

    outputs = run_pipeline(
        args.input_audio,
        args.output_dir,
        args.grid_division,
        title=args.title,
        composer=args.composer,
        creator=args.creator,
        sections_json=args.sections_json,
        render_pdf=not args.no_pdf,
        musescore_path=args.musescore_path,
    )
    print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
