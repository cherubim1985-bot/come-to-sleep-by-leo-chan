#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import wave
from array import array
from pathlib import Path
from shutil import which


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch Edge TTS runner for meditation voiceovers.")
    parser.add_argument("--text", default="", help="Single text segment to synthesize.")
    parser.add_argument("--blocks-file", default="", help="JSON file containing spoken block objects.")
    parser.add_argument("--output", required=True, help="Output wav path.")
    parser.add_argument("--temp-dir", required=True, help="Temporary work directory.")
    parser.add_argument("--voice", default="en-US-JennyNeural", help="Edge TTS voice name.")
    parser.add_argument("--rate", default="-15%", help="Speech rate adjustment.")
    parser.add_argument("--volume", default="+0%", help="Volume adjustment.")
    parser.add_argument("--pitch", default="-8Hz", help="Pitch adjustment.")
    parser.add_argument("--sample-rate", type=int, default=24000, help="Target wav sample rate.")
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
    raise RuntimeError("找不到 ffmpeg，无法转换 Edge TTS 音频。")


def load_blocks(args: argparse.Namespace) -> list[dict]:
    if args.blocks_file:
        payload = json.loads(Path(args.blocks_file).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("blocks-file 必须是数组。")
        blocks: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                raise RuntimeError("spoken block 必须是对象。")
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            pause_after_ms = int(item.get("pause_after_ms", 0) or 0)
            blocks.append({"text": text, "pause_after_ms": max(0, pause_after_ms)})
        if not blocks:
            raise RuntimeError("blocks-file 中没有有效文本。")
        return blocks
    text = args.text.strip()
    if not text:
        raise RuntimeError("必须提供 --text 或 --blocks-file。")
    return [{"text": text, "pause_after_ms": 0}]


async def synthesize_segment(text: str, output_path: Path, args: argparse.Namespace) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice=args.voice,
        rate=args.rate,
        volume=args.volume,
        pitch=args.pitch,
    )
    await communicate.save(str(output_path))


def convert_to_wav(ffmpeg_bin: str, source_path: Path, output_path: Path, sample_rate: int) -> None:
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(source_path),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def build_silence(frame_count: int) -> bytes:
    if frame_count <= 0:
        return b""
    return array("h", [0] * frame_count).tobytes()


def concatenate_wavs(segment_files: list[tuple[Path, int]], output_path: Path) -> None:
    if not segment_files:
        raise RuntimeError("没有可拼接的 wav 文件。")

    with wave.open(str(segment_files[0][0]), "rb") as first:
        params = first.getparams()

    with wave.open(str(output_path), "wb") as merged:
        merged.setparams(params)
        frame_rate = params.framerate
        sample_width = params.sampwidth
        channels = params.nchannels
        for wav_path, pause_after_ms in segment_files:
            with wave.open(str(wav_path), "rb") as source:
                if source.getnchannels() != channels or source.getsampwidth() != sample_width or source.getframerate() != frame_rate:
                    raise RuntimeError(f"WAV 参数不一致，无法拼接: {wav_path}")
                merged.writeframes(source.readframes(source.getnframes()))
            if pause_after_ms > 0:
                pause_frames = int(frame_rate * (pause_after_ms / 1000))
                merged.writeframes(build_silence(pause_frames * channels))


def main() -> int:
    args = parse_args()
    blocks = load_blocks(args)
    temp_dir = Path(args.temp_dir).resolve()
    output_path = Path(args.output).resolve()
    ffmpeg_bin = resolve_ffmpeg()

    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    segment_dir = temp_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)

    rendered_segments: list[tuple[Path, int]] = []
    for index, block in enumerate(blocks, start=1):
        mp3_path = segment_dir / f"segment_{index:03d}.mp3"
        wav_path = segment_dir / f"segment_{index:03d}.wav"
        asyncio.run(synthesize_segment(block["text"], mp3_path, args))
        convert_to_wav(ffmpeg_bin, mp3_path, wav_path, args.sample_rate)
        rendered_segments.append((wav_path, int(block.get("pause_after_ms", 0))))

    concatenate_wavs(rendered_segments, output_path)
    print(f"Generated Edge TTS voiceover at {output_path}")
    print(f"Segment count: {len(rendered_segments)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
