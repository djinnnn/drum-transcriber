from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from pipeline.detect import DRUM_KEYS, DrumHits


@dataclass(frozen=True)
class QuantizedHit:
    instrument: str
    time: float
    bar: int
    slot: int
    beat: int
    grid_time: float


@dataclass(frozen=True)
class QuantizedChart:
    bpm: float
    beats: list[float]
    grid_division: int
    total_bars: int
    hits: list[QuantizedHit]


def detect_beats(audio_path: str | Path) -> tuple[float, list[float]]:
    """Return BPM and beat times using madmom, with librosa as a fallback."""
    path = str(Path(audio_path).expanduser().resolve())

    try:
        from madmom.features.beats import DBNBeatTrackingProcessor, RNNBeatProcessor

        activations = RNNBeatProcessor()(path)
        beats = DBNBeatTrackingProcessor(fps=100)(activations)
        beat_list = [float(value) for value in beats]
        return _bpm_from_beats(beat_list), beat_list
    except Exception as madmom_error:
        try:
            import librosa

            y, sr = librosa.load(path, mono=True)
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
            tempo_value = float(np.asarray(tempo).reshape(-1)[0])
            return tempo_value, [float(value) for value in beats]
        except Exception as librosa_error:
            raise RuntimeError(
                f"Beat tracking failed with madmom ({madmom_error}) and librosa ({librosa_error})."
            ) from librosa_error


def quantize_hits(
    hits: DrumHits,
    beats: list[float],
    bpm: float | None = None,
    grid_division: int = 16,
    beats_per_bar: int = 4,
) -> QuantizedChart:
    if len(beats) < 2:
        if bpm is None:
            bpm = 120.0
        seconds_per_beat = 60.0 / bpm
        max_hit = max((time for values in hits.values() for time in values), default=0.0)
        beats = [index * seconds_per_beat for index in range(int(max_hit / seconds_per_beat) + beats_per_bar + 2)]
    else:
        bpm = bpm or _bpm_from_beats(beats)

    slots_per_beat = grid_division // 4
    quantized: list[QuantizedHit] = []
    occupied: set[tuple[str, int, int]] = set()

    for instrument in DRUM_KEYS:
        for time in hits.get(instrument, []):
            beat_index = _nearest_beat_index(beats, time)
            local_interval = _beat_interval(beats, beat_index, bpm)
            offset_slots = round((time - beats[beat_index]) / local_interval * slots_per_beat)
            absolute_slot = beat_index * slots_per_beat + offset_slots
            if absolute_slot < 0:
                absolute_slot = 0
            bar = absolute_slot // (beats_per_bar * slots_per_beat) + 1
            slot = absolute_slot % (beats_per_bar * slots_per_beat)
            beat = slot // slots_per_beat + 1
            grid_time = beats[0] + absolute_slot * (60.0 / bpm / slots_per_beat)
            key = (instrument, bar, slot)
            if key in occupied:
                continue
            occupied.add(key)
            quantized.append(QuantizedHit(instrument, float(time), int(bar), int(slot), int(beat), float(grid_time)))

    quantized.sort(key=lambda hit: (hit.bar, hit.slot, hit.instrument))
    beat_based_bars = max(1, int(np.ceil(len(beats) / float(beats_per_bar))))
    total_bars = max(max((hit.bar for hit in quantized), default=1), beat_based_bars)
    return QuantizedChart(float(bpm), [float(value) for value in beats], grid_division, total_bars, quantized)


def chart_to_dict(chart: QuantizedChart) -> dict:
    return {
        "bpm": chart.bpm,
        "beats": chart.beats,
        "grid_division": chart.grid_division,
        "total_bars": chart.total_bars,
        "hits": [asdict(hit) for hit in chart.hits],
    }


def chart_from_dict(data: dict) -> QuantizedChart:
    return QuantizedChart(
        bpm=float(data["bpm"]),
        beats=[float(value) for value in data.get("beats", [])],
        grid_division=int(data["grid_division"]),
        total_bars=int(data["total_bars"]),
        hits=[QuantizedHit(**hit) for hit in data.get("hits", [])],
    )


def _nearest_beat_index(beats: list[float], time: float) -> int:
    index = int(np.searchsorted(beats, time))
    if index <= 0:
        return 0
    if index >= len(beats):
        return len(beats) - 1
    return index if abs(beats[index] - time) < abs(beats[index - 1] - time) else index - 1


def _beat_interval(beats: list[float], index: int, bpm: float) -> float:
    if index + 1 < len(beats):
        return max(0.05, beats[index + 1] - beats[index])
    if index > 0:
        return max(0.05, beats[index] - beats[index - 1])
    return 60.0 / bpm


def _bpm_from_beats(beats: list[float]) -> float:
    intervals = np.diff(np.asarray(beats, dtype=float))
    intervals = intervals[(intervals > 0.2) & (intervals < 2.0)]
    if intervals.size == 0:
        return 120.0
    return float(60.0 / np.median(intervals))


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect beats and quantize drum hits to a 16th-note grid.")
    parser.add_argument("audio")
    parser.add_argument("hits_json")
    parser.add_argument("--output-json", default="output/quantized.json")
    parser.add_argument("--grid-division", type=int, default=16)
    args = parser.parse_args()

    hits = json.loads(Path(args.hits_json).read_text(encoding="utf-8"))
    bpm, beats = detect_beats(args.audio)
    chart = quantize_hits(hits, beats, bpm, args.grid_division)
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(chart_to_dict(chart), indent=2), encoding="utf-8")
    print(json.dumps({"bpm": chart.bpm, "total_bars": chart.total_bars}, indent=2))


if __name__ == "__main__":
    main()
