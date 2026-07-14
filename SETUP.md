# Setup

This project uses a Python pipeline:

```text
Demucs -> ADTLib -> madmom -> pretty_midi -> music21 MusicXML -> MuseScore PDF
```

## Create an isolated venv

```bash
cd drum-transcriber
UV_CACHE_DIR=.uv-cache uv venv .venv --python 3.9
source .venv/bin/activate
python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel cython
python -m pip install -r requirements.txt
python -m pip install "git+https://github.com/carlsouthall/ADTLib.git"
```

`madmom` and `ADTLib` are old packages. Keep all fixes inside `.venv`; do not install them into the system Python.

On Apple Silicon, ADTLib's TensorFlow 1 style code is handled by a compatibility shim in `pipeline/detect.py`; TensorFlow 2.15.x works.

## MuseScore

To render PDF automatically, install MuseScore 4 and make the CLI available as one of:

- `musescore4`
- `mscore`
- `/Applications/MuseScore Studio 4.app/Contents/MacOS/mscore`

If the CLI is not found, run with `--no-pdf` and open `song.musicxml` manually in MuseScore.

## Run

```bash
source .venv/bin/activate
python main.py "/path/to/song.mp3" --output-dir output/song --title "Song Title" --composer "Artist"
```

With manual rehearsal marks:

```bash
python main.py "/path/to/song.mp3" --output-dir output/song --sections-json sections.json
```

Expected outputs:

- `output/song/drums.wav`
- `output/song/hits.json`
- `output/song/quantized.json`
- `output/song/song.mid`
- `output/song/song.musicxml`
- `output/song/song.pdf` when MuseScore CLI is available

## Individual stages

```bash
python -m pipeline.separate song.mp3 --output-dir output/song
python -m pipeline.detect output/song/drums.wav --output-json output/song/hits.json
python -m pipeline.beat_grid song.mp3 output/song/hits.json --output-json output/song/quantized.json
python -m pipeline.to_midi output/song/quantized.json --output-midi output/song/song.mid
python -m pipeline.to_score output/song/quantized.json --output-musicxml output/song/song.musicxml --output-pdf output/song/song.pdf
```
