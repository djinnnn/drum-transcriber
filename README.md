# 架子鼓自动扒谱工具

一个本地 Python pipeline，用于从音频生成可交给专业刻谱引擎排版的鼓谱文件。

核心流程：

```text
MP3/WAV -> Demucs 鼓轨分离 -> ADTLib KD/SD/HH 检测 -> madmom 节拍量化
        -> pretty_midi 输出 MIDI
        -> music21 输出 MusicXML
        -> MuseScore 4 CLI 渲染 PDF
```

## 当前能力

- 使用 Demucs `htdemucs` 分离鼓轨
- 使用 ADTLib 预训练模型检测：
  - `KD` Kick Drum / 底鼓
  - `SD` Snare Drum / 军鼓
  - `HH` Hi-Hat / 踩镲
- 使用 madmom 检测 BPM 和 beat grid
- 输出 `song.mid`
- 输出 `song.musicxml`
- 如本机安装 MuseScore 4 CLI，则输出 `song.pdf`

## 安装

```bash
cd drum-transcriber
UV_CACHE_DIR=.uv-cache uv venv .venv --python 3.9
source .venv/bin/activate
python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel cython
python -m pip install -r requirements.txt
python -m pip install "git+https://github.com/carlsouthall/ADTLib.git"
```

如果要直接渲染 PDF，还需要安装 MuseScore 4，并确保命令行可执行文件可用。没有 MuseScore 时，仍会生成 `song.musicxml`，可以手动用 MuseScore 打开后导出 PDF。

## 一键处理

```bash
source .venv/bin/activate
python main.py "/path/to/song.mp3" --output-dir output/song --title "Song Title" --composer "Artist"
```

如果暂时没有 MuseScore：

```bash
python main.py "/path/to/song.mp3" --output-dir output/song --no-pdf
```

如果有人工标注的曲式段落：

```bash
python main.py "/path/to/song.mp3" --output-dir output/song --sections-json sections.json
```

输出：

- `drums.wav`
- `hits.json`
- `quantized.json`
- `song.mid`
- `song.musicxml`
- `song.pdf`，仅在 MuseScore CLI 可用时生成

## 单独生成 MusicXML / PDF

```bash
python -m pipeline.to_score output/song/quantized.json \
  --output-musicxml output/song/song.musicxml \
  --output-pdf output/song/song.pdf \
  --title "Song Title" \
  --composer "Artist"
```

段落标记可以用 JSON 文件传入：

```json
{
  "1": "前",
  "3": "A1",
  "19": "B1",
  "59": "间1",
  "67": "C1"
}
```

然后：

```bash
python -m pipeline.to_score output/song/quantized.json \
  --output-musicxml output/song/song.musicxml \
  --sections-json sections.json
```

## 备注

ADTLib 是 TensorFlow 1 风格老代码。本项目在 `pipeline/detect.py` 中做了 TensorFlow 2.15 兼容 shim，并修补了它在新版 numpy 下的峰值去重问题。

目前 ADTLib 只稳定输出 KD/SD/HH。完整鼓谱里的 Crash/Ride/Tom/Open Hat 等需要接入更强的多类别鼓转录模型，或增加音色规则后处理。
