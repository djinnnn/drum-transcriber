from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

DrumHits = dict[str, list[float]]
DRUM_KEYS = ("KD", "SD", "HH")


def detect_drums(drums_wav: str | Path, output_json: str | Path | None = None) -> DrumHits:
    """Detect kick/snare/hi-hat timestamps with ADTLib.

    ADTLib has circulated with a few different entrypoints. This adapter tries
    the common Python module style first, then falls back to a CLI executable if
    one exists in the environment.
    """
    audio_path = Path(drums_wav).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Drum stem not found: {audio_path}")

    raw = _try_python_api(audio_path)
    if raw is None:
        raw = _try_cli(audio_path)
    if raw is None:
        raise RuntimeError(
            "ADTLib could not be called. Install carlsouthall/ADTLib in the venv, then update "
            "pipeline/detect.py:_try_python_api if your installed package exposes a different API."
        )

    hits = normalize_hits(raw)
    if output_json:
        out_path = Path(output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(hits, indent=2), encoding="utf-8")
    return hits


def normalize_hits(raw: Any) -> DrumHits:
    """Normalize common ADTLib result shapes into {'KD': [...], 'SD': [...], 'HH': [...]}."""
    if isinstance(raw, dict):
        aliases = {
            "KD": ("KD", "Kick", "kick", "bd", "bass", "Bass Drum"),
            "SD": ("SD", "Snare", "snare", "sn", "Snare Drum"),
            "HH": ("HH", "Hihat", "HiHat", "hihat", "hi_hat", "hh", "Closed Hi-Hat"),
        }
        normalized: DrumHits = {key: [] for key in DRUM_KEYS}
        for target, names in aliases.items():
            for name in names:
                if name in raw:
                    normalized[target] = _float_list(raw[name])
                    break
        return normalized

    if isinstance(raw, list):
        normalized = {key: [] for key in DRUM_KEYS}
        for item in raw:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("class") or item.get("instrument") or "").upper()
            time = item.get("time", item.get("timestamp", item.get("onset")))
            if time is None:
                continue
            if label in normalized:
                normalized[label].append(float(time))
        return normalized

    raise TypeError(f"Unsupported ADTLib result type: {type(raw)!r}")


def _float_list(values: Any) -> list[float]:
    return sorted(float(value) for value in values)


def _try_python_api(audio_path: Path) -> Any | None:
    _enable_tensorflow_v1_compat()
    try:
        import ADTLib

        _patch_adtlib_postprocess(ADTLib)
        return ADTLib.ADT([str(audio_path)], text="no", tab="no")[0]
    except ImportError:
        pass
    except Exception as exc:
        raise RuntimeError(f"ADTLib Python API failed: {exc}") from exc

    candidates = ["ADTLib", "adtlib", "adt"]
    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue

        for attr in ("transcribe", "detect", "predict", "process_file"):
            func = getattr(module, attr, None)
            if callable(func):
                return func(str(audio_path))

        for class_name in ("ADT", "Transcriber", "DrumTranscriber"):
            cls = getattr(module, class_name, None)
            if cls is None:
                continue
            instance = cls()
            for method_name in ("transcribe", "detect", "predict", "process_file"):
                method = getattr(instance, method_name, None)
                if callable(method):
                    return method(str(audio_path))
    return None


def _enable_tensorflow_v1_compat() -> None:
    """Make ADTLib's TensorFlow 1 imports work on a TensorFlow 2 install."""
    try:
        import tensorflow as tf
    except ImportError:
        return

    tf.compat.v1.disable_eager_execution()
    compat_names = [
        "Session",
        "placeholder",
        "reset_default_graph",
        "global_variables_initializer",
        "trainable_variables",
        "variable_scope",
        "random_normal",
    ]
    for name in compat_names:
        if not hasattr(tf, name):
            setattr(tf, name, getattr(tf.compat.v1, name))
    if not hasattr(tf.train, "Saver"):
        tf.train.Saver = tf.compat.v1.train.Saver
    if not hasattr(tf.train, "GradientDescentOptimizer"):
        tf.train.GradientDescentOptimizer = tf.compat.v1.train.GradientDescentOptimizer
    if not hasattr(tf.train, "AdamOptimizer"):
        tf.train.AdamOptimizer = tf.compat.v1.train.AdamOptimizer
    if not hasattr(tf.train, "RMSPropOptimizer"):
        tf.train.RMSPropOptimizer = tf.compat.v1.train.RMSPropOptimizer
    if not hasattr(tf.nn, "dynamic_rnn"):
        tf.nn.dynamic_rnn = tf.compat.v1.nn.dynamic_rnn
    if not hasattr(tf.nn, "bidirectional_dynamic_rnn"):
        tf.nn.bidirectional_dynamic_rnn = tf.compat.v1.nn.bidirectional_dynamic_rnn

    contrib = types.ModuleType("tensorflow.contrib")
    contrib.rnn = tf.compat.v1.nn.rnn_cell
    sys.modules.setdefault("tensorflow.contrib", contrib)
    sys.modules.setdefault("tensorflow.contrib.rnn", contrib.rnn)


def _patch_adtlib_postprocess(ADTLib: Any) -> None:
    """Patch ADTLib's old numpy-incompatible peak thinning code."""
    import numpy as np

    def mean_pp_mm(track: Any, lambda_value: float, minimum: float, maximum: float, hop: int = 512, fs: int = 44100, dif: float = 0.05):
        threshold = float(np.mean(track) * lambda_value)
        if maximum != 0:
            threshold = min(threshold, float(maximum))
        if minimum != 0:
            threshold = max(threshold, float(minimum))

        padded = np.zeros(len(track) + 2)
        padded[1 : len(track) + 1] = track
        peaks: list[tuple[int, float]] = []
        for index in range(len(padded) - 2):
            center = padded[index + 1]
            if center > padded[index] and center >= padded[index + 2] and center > threshold:
                peaks.append((index + 1, float(center)))

        selected: list[tuple[int, float]] = []
        for frame, value in peaks:
            time = (frame * hop) / float(fs)
            if selected and abs(time - (selected[-1][0] * hop) / float(fs)) < dif:
                if value > selected[-1][1]:
                    selected[-1] = (frame, value)
            else:
                selected.append((frame, value))

        return np.asarray([(frame * hop) / float(fs) for frame, _ in selected], dtype=float)

    ADTLib.utils.meanPPmm = mean_pp_mm


def _try_cli(audio_path: Path) -> Any | None:
    for executable in ("adtlib", "ADTLib", "adt"):
        try:
            completed = subprocess.run(
                [executable, str(audio_path), "--json"],
                check=True,
                text=True,
                capture_output=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{executable} ran, but did not emit JSON.") from exc
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect KD/SD/HH onsets from a drums stem using ADTLib.")
    parser.add_argument("drums_wav")
    parser.add_argument("--output-json", default="output/hits.json")
    args = parser.parse_args()
    print(json.dumps(detect_drums(args.drums_wav, args.output_json), indent=2))


if __name__ == "__main__":
    main()
