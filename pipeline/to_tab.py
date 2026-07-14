from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.beat_grid import QuantizedChart, chart_from_dict

TAB_ROWS = (("HH", "x"), ("SD", "o"), ("KD", "o"))


def chart_to_ascii(chart: QuantizedChart) -> str:
    slots_per_bar = chart.grid_division
    bars: list[str] = [f"Tempo: {chart.bpm:.1f} BPM", f"Grid: 1/{chart.grid_division}", ""]
    by_bar: dict[int, dict[str, list[str]]] = {}

    for bar in range(1, chart.total_bars + 1):
        by_bar[bar] = {instrument: ["-" for _ in range(slots_per_bar)] for instrument, _ in TAB_ROWS}

    for hit in chart.hits:
        if hit.instrument in by_bar.get(hit.bar, {}) and 0 <= hit.slot < slots_per_bar:
            mark = dict(TAB_ROWS)[hit.instrument]
            by_bar[hit.bar][hit.instrument][hit.slot] = mark

    for bar in range(1, chart.total_bars + 1):
        bars.append(f"Bar {bar}")
        for instrument, _ in TAB_ROWS:
            bars.append(f"{instrument}|{''.join(by_bar[bar][instrument])}|")
        bars.append("")
    return "\n".join(bars)


def write_tab(chart: QuantizedChart, output_txt: str | Path) -> Path:
    out_path = Path(output_txt)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(chart_to_ascii(chart), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a quantized drum chart as ASCII tab.")
    parser.add_argument("quantized_json")
    parser.add_argument("--output-txt", default="output/song_tab.txt")
    args = parser.parse_args()
    chart = chart_from_dict(json.loads(Path(args.quantized_json).read_text(encoding="utf-8")))
    print(write_tab(chart, args.output_txt))


if __name__ == "__main__":
    main()
