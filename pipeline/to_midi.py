from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.beat_grid import QuantizedChart, chart_from_dict

GM_DRUM_MAP = {
    "KD": 36,
    "SD": 38,
    "HH": 42,
}


def write_midi(chart: QuantizedChart, output_midi: str | Path) -> Path:
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(initial_tempo=chart.bpm)
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    seconds_per_slot = 60.0 / chart.bpm / (chart.grid_division // 4)
    note_length = max(0.04, seconds_per_slot * 0.75)

    for hit in chart.hits:
        pitch = GM_DRUM_MAP.get(hit.instrument)
        if pitch is None:
            continue
        start = max(0.0, hit.grid_time)
        drums.notes.append(
            pretty_midi.Note(
                velocity=96,
                pitch=pitch,
                start=start,
                end=start + note_length,
            )
        )

    midi.instruments.append(drums)
    out_path = Path(output_midi)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(out_path))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a quantized drum chart as a General MIDI drum track.")
    parser.add_argument("quantized_json")
    parser.add_argument("--output-midi", default="output/song.mid")
    args = parser.parse_args()
    chart = chart_from_dict(json.loads(Path(args.quantized_json).read_text(encoding="utf-8")))
    print(write_midi(chart, args.output_midi))


if __name__ == "__main__":
    main()
