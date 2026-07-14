from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pipeline.beat_grid import QuantizedChart, chart_from_dict


@dataclass(frozen=True)
class DrumNotation:
    display_step: str
    display_octave: int
    notehead: str
    stem_direction: str


DRUM_NOTATION: dict[str, DrumNotation] = {
    # MusicXML display positions are chosen for standard drum-set staff layout.
    "HH": DrumNotation("G", 5, "x", "up"),
    "OH": DrumNotation("G", 5, "x", "up"),
    "SD": DrumNotation("C", 5, "normal", "up"),
    "KD": DrumNotation("F", 4, "normal", "down"),
    "HHP": DrumNotation("D", 4, "x", "down"),
    "HT": DrumNotation("E", 5, "normal", "up"),
    "MT": DrumNotation("D", 5, "normal", "up"),
    "FT": DrumNotation("A", 4, "normal", "down"),
    "RD": DrumNotation("F", 5, "x", "up"),
    "CC": DrumNotation("A", 5, "x", "up"),
}


def write_musicxml(
    chart: QuantizedChart,
    output_musicxml: str | Path,
    title: str = "Drum Transcription",
    composer: str = "",
    creator: str = "",
    sections: dict[int, str] | None = None,
) -> Path:
    from music21 import clef, expressions, layout, metadata, meter, note, percussion, stream, tempo

    out_path = Path(output_musicxml)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    score = stream.Score()
    score.metadata = metadata.Metadata()
    score.metadata.title = title
    if composer:
        score.metadata.composer = composer
    if creator:
        score.metadata.movementName = creator

    part = stream.Part(id="Drumset")
    part.partName = "Drumset"
    part.insert(0, clef.PercussionClef())
    part.insert(0, meter.TimeSignature("4/4"))
    part.insert(0, tempo.MetronomeMark(number=round(chart.bpm)))

    slots_per_bar = chart.grid_division
    ql_per_slot = 4.0 / slots_per_bar
    hits_by_bar_slot: dict[tuple[int, int], list[str]] = {}
    for hit in chart.hits:
        if hit.instrument not in DRUM_NOTATION:
            continue
        hits_by_bar_slot.setdefault((hit.bar, hit.slot), []).append(hit.instrument)

    sections = sections or {}
    for bar_number in range(1, chart.total_bars + 1):
        measure = stream.Measure(number=bar_number)
        if bar_number in sections:
            measure.insert(0, expressions.RehearsalMark(sections[bar_number]))

        slot = 0
        while slot < slots_per_bar:
            instruments = hits_by_bar_slot.get((bar_number, slot), [])
            if instruments:
                element = _make_percussion_element(instruments, ql_per_slot)
                measure.append(element)
                slot += 1
                continue

            rest_slots = 1
            while slot + rest_slots < slots_per_bar and not hits_by_bar_slot.get((bar_number, slot + rest_slots)):
                rest_slots += 1
            rest = note.Rest(quarterLength=ql_per_slot * rest_slots)
            measure.append(rest)
            slot += rest_slots

        part.append(measure)

    _apply_system_layout(part)
    score.insert(0, part)
    score.write("musicxml", fp=str(out_path))
    return out_path


def render_pdf_with_musescore(
    musicxml_path: str | Path,
    output_pdf: str | Path,
    musescore_path: str | Path | None = None,
) -> Path:
    executable = _find_musescore(musescore_path)
    if executable is None:
        raise FileNotFoundError(
            "MuseScore CLI not found. Install MuseScore 4 and pass --musescore-path, "
            "or open the generated .musicxml in MuseScore manually and export PDF."
        )

    out_path = Path(output_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(executable), str(musicxml_path), "-o", str(out_path)], check=True)
    return out_path


def write_score_outputs(
    chart: QuantizedChart,
    output_musicxml: str | Path,
    output_pdf: str | Path | None = None,
    title: str = "Drum Transcription",
    composer: str = "",
    creator: str = "",
    sections: dict[int, str] | None = None,
    musescore_path: str | Path | None = None,
) -> dict[str, Path | None]:
    musicxml_path = write_musicxml(chart, output_musicxml, title, composer, creator, sections)
    pdf_path: Path | None = None
    if output_pdf is not None:
        pdf_path = render_pdf_with_musescore(musicxml_path, output_pdf, musescore_path)
    return {"musicxml": musicxml_path, "pdf": pdf_path}


def _make_percussion_element(instruments: Iterable[str], quarter_length: float):
    from music21 import note, percussion

    notes = []
    for instrument in sorted(set(instruments), key=_instrument_sort_key):
        spec = DRUM_NOTATION[instrument]
        unpitched = note.Unpitched(quarterLength=quarter_length)
        unpitched.displayStep = spec.display_step
        unpitched.displayOctave = spec.display_octave
        unpitched.notehead = spec.notehead
        unpitched.stemDirection = spec.stem_direction
        notes.append(unpitched)

    if len(notes) == 1:
        return notes[0]

    chord = percussion.PercussionChord(notes)
    chord.quarterLength = quarter_length
    chord.stemDirection = "up" if any(n.stemDirection == "up" for n in notes) else "down"
    return chord


def _instrument_sort_key(instrument: str) -> int:
    order = ["CC", "RD", "OH", "HH", "SD", "HT", "MT", "FT", "KD", "HHP"]
    try:
        return order.index(instrument)
    except ValueError:
        return len(order)


def _apply_system_layout(part) -> None:
    from music21 import layout

    for measure in part.getElementsByClass("Measure"):
        number = int(measure.number or 0)
        if number == 1:
            measure.insert(0, layout.SystemLayout(isNew=True))
        elif (number - 1) % 4 == 0:
            measure.insert(0, layout.SystemLayout(isNew=True))


def _find_musescore(explicit_path: str | Path | None = None) -> Path | None:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        return path if path.exists() else None

    command_names = ["musescore4", "mscore", "musescore", "MuseScore"]
    for command in command_names:
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)

    mac_candidates = [
        "/Applications/MuseScore Studio 4.app/Contents/MacOS/mscore",
        "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
        "/Applications/MuseScore Studio.app/Contents/MacOS/mscore",
        "/Applications/MuseScore.app/Contents/MacOS/mscore",
    ]
    for candidate in mac_candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def load_sections(path: str | Path | None) -> dict[int, str]:
    if path is None:
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return {int(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        return {int(item["bar"]): str(item["label"]) for item in raw}
    raise ValueError("Sections file must be a JSON object {bar: label} or a list of {bar, label}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a quantized drum chart to MusicXML and optionally PDF via MuseScore.")
    parser.add_argument("quantized_json")
    parser.add_argument("--output-musicxml", default="output/song.musicxml")
    parser.add_argument("--output-pdf")
    parser.add_argument("--title", default="Drum Transcription")
    parser.add_argument("--composer", default="")
    parser.add_argument("--creator", default="")
    parser.add_argument("--sections-json")
    parser.add_argument("--musescore-path")
    args = parser.parse_args()

    chart = chart_from_dict(json.loads(Path(args.quantized_json).read_text(encoding="utf-8")))
    outputs = write_score_outputs(
        chart,
        args.output_musicxml,
        args.output_pdf,
        title=args.title,
        composer=args.composer,
        creator=args.creator,
        sections=load_sections(args.sections_json),
        musescore_path=args.musescore_path,
    )
    print(json.dumps({key: str(value) if value else None for key, value in outputs.items()}, indent=2))


if __name__ == "__main__":
    main()
