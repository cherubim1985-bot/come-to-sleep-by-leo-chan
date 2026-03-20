#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import which


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IndexTTS local batch runner.")
    parser.add_argument("--text", default="", help="Text to synthesize.")
    parser.add_argument("--texts-file", default="", help="JSON file containing a list of text segments.")
    parser.add_argument("--reference-audio", required=True, help="Reference voice audio.")
    parser.add_argument("--output", required=True, help="Output wav path.")
    parser.add_argument("--model-dir", required=True, help="IndexTTS model directory.")
    parser.add_argument("--config-path", required=True, help="IndexTTS config path.")
    parser.add_argument("--temp-dir", required=True, help="Temporary work directory.")
    parser.add_argument("--repo-dir", default="third_party/index-tts", help="IndexTTS repo directory.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"], help="Inference device.")
    return parser.parse_args()


def resolve_ffmpeg() -> str:
    candidates = [
        Path(sys.executable).resolve().parent / "ffmpeg",
        Path("/tmp/cosyvoice-conda/bin/ffmpeg"),
        Path("/tmp/openvoice-conda/bin/ffmpeg"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    ffmpeg_bin = which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    raise RuntimeError("找不到 ffmpeg，无法预处理参考音频。")


def load_segments(args: argparse.Namespace) -> list[str]:
    if args.texts_file:
        payload = json.loads(Path(args.texts_file).read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not all(isinstance(item, str) and item.strip() for item in payload):
            raise RuntimeError("texts-file 必须是非空字符串数组。")
        return [item.strip() for item in payload]
    text = args.text.strip()
    if not text:
        raise RuntimeError("必须提供 --text 或 --texts-file。")
    return [text]


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    model_dir = Path(args.model_dir).resolve()
    config_path = Path(args.config_path).resolve()
    temp_dir = Path(args.temp_dir).resolve()
    reference_audio = Path(args.reference_audio).resolve()
    output_path = Path(args.output).resolve()

    if not repo_dir.exists():
        raise SystemExit(f"IndexTTS repo not found: {repo_dir}")
    if not model_dir.exists():
        raise SystemExit(f"IndexTTS model directory not found: {model_dir}")
    if not config_path.exists():
        raise SystemExit(f"IndexTTS config not found: {config_path}")
    if not reference_audio.exists():
        raise SystemExit(f"Reference audio not found: {reference_audio}")

    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    segment_dir = temp_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)

    cleaned_reference = temp_dir / "reference.wav"
    ffmpeg_bin = resolve_ffmpeg()
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(reference_audio),
            "-ac",
            "1",
            "-ar",
            "24000",
            str(cleaned_reference),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    sys.path.insert(0, str(repo_dir))
    os.chdir(repo_dir)
    os.environ.setdefault("HF_HUB_CACHE", str((model_dir / "hf_cache").resolve()))

    from indextts.infer import IndexTTS

    segments = load_segments(args)
    tts = IndexTTS(cfg_path=str(config_path), model_dir=str(model_dir), use_fp16=False, device=args.device)

    generated_files: list[Path] = []
    for index, text in enumerate(segments, start=1):
        segment_output = segment_dir / f"segment_{index:03d}.wav"
        tts.infer(audio_prompt=str(cleaned_reference), text=text, output_path=str(segment_output), verbose=False)
        generated_files.append(segment_output)

    import numpy as np
    import soundfile as sf

    audio_chunks = []
    sample_rate = None
    for path in generated_files:
        audio, current_rate = sf.read(str(path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sample_rate is None:
            sample_rate = current_rate
        elif current_rate != sample_rate:
            raise RuntimeError(f"sample rate mismatch for {path}: {current_rate} != {sample_rate}")
        audio_chunks.append(audio)
        audio_chunks.append(np.zeros(int(sample_rate * 0.35), dtype="float32"))

    merged = np.concatenate(audio_chunks[:-1]) if len(audio_chunks) > 1 else audio_chunks[0]
    sf.write(str(output_path), merged, sample_rate)
    print(f"Generated IndexTTS voiceover at {output_path}")
    print(f"Segment count: {len(generated_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
