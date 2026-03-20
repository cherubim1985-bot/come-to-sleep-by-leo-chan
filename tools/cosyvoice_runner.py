#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from shutil import which


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CosyVoice2 local zero-shot runner.")
    parser.add_argument("--text", default="", help="Text to synthesize.")
    parser.add_argument("--texts-file", default="", help="JSON file containing a list of text segments.")
    parser.add_argument("--reference-audio", required=True, help="Reference voice audio.")
    parser.add_argument("--prompt-text", default="", help="Transcript of the reference audio.")
    parser.add_argument("--output", required=True, help="Output wav path.")
    parser.add_argument("--model-dir", required=True, help="CosyVoice model directory.")
    parser.add_argument("--temp-dir", required=True, help="Temporary work directory.")
    parser.add_argument("--repo-dir", default="third_party/CosyVoice", help="CosyVoice repo directory.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"], help="Inference device.")
    return parser.parse_args()


def transcribe_reference_audio(reference_wav: Path) -> str:
    import whisper

    model = whisper.load_model("base")
    result = model.transcribe(str(reference_wav), language="zh", fp16=False)
    text = str(result.get("text", "")).strip()
    if not text:
        raise RuntimeError("Whisper 未识别出参考音频文字。")
    return text


def resolve_ffmpeg() -> str:
    candidates = [
        Path(sys.executable).resolve().parent / "ffmpeg",
        Path("/tmp/cosyvoice-conda/bin/ffmpeg"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    ffmpeg_bin = which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    raise RuntimeError("找不到 ffmpeg，无法预处理参考音频。")


def concatenate_wav_files(source_files: list[Path], output_path: Path) -> None:
    if not source_files:
        raise ValueError("No wav files to concatenate.")
    if len(source_files) == 1:
        output_path.write_bytes(source_files[0].read_bytes())
        return
    import numpy as np
    import soundfile as sf

    audio_chunks = []
    sample_rate = None
    channels = None
    for source_file in source_files:
        audio, current_rate = sf.read(str(source_file), always_2d=True)
        if sample_rate is None:
            sample_rate = current_rate
            channels = audio.shape[1]
        elif current_rate != sample_rate or audio.shape[1] != channels:
            raise ValueError(f"WAV parameters do not match for concatenation: {source_file}")
        audio_chunks.append(audio)
    merged = np.concatenate(audio_chunks, axis=0)
    sf.write(str(output_path), merged, sample_rate)


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


def patch_cosyvoice_device(torch, model_module, device_name: str) -> None:
    if device_name != "mps":
        if hasattr(torch.backends, "mps"):
            torch.backends.mps.is_available = lambda: False
        return
    if not hasattr(torch.backends, "mps") or not torch.backends.mps.is_available():
        raise RuntimeError("当前机器不可用 MPS，无法测试本机 GPU。")

    def patched_init(self, llm, flow, hift, fp16=False):
        self.device = torch.device("mps")
        self.llm = llm
        self.flow = flow
        self.hift = hift
        self.fp16 = False
        if self.__class__.__name__ == "CosyVoice2Model":
            self.token_hop_len = 25
            self.token_max_hop_len = 4 * self.token_hop_len
            self.stream_scale_factor = 2
            self.mel_cache_len = 8
            self.source_cache_len = int(self.mel_cache_len * 480)
            self.speech_window = np.hamming(2 * self.source_cache_len)
            self.llm_context = nullcontext()
            self.lock = threading.Lock()
            self.tts_speech_token_dict = {}
            self.llm_end_dict = {}
            self.hift_cache_dict = {}
            self.silent_tokens = []
            return
        self.token_min_hop_len = 2 * self.flow.input_frame_rate
        self.token_max_hop_len = 4 * self.flow.input_frame_rate
        self.token_overlap_len = 20
        self.mel_overlap_len = int(self.token_overlap_len / self.flow.input_frame_rate * 22050 / 256)
        self.mel_window = np.hamming(2 * self.mel_overlap_len)
        self.mel_cache_len = 20
        self.source_cache_len = int(self.mel_cache_len * 256)
        self.speech_window = np.hamming(2 * self.source_cache_len)
        self.stream_scale_factor = 1
        self.llm_context = nullcontext()
        self.lock = threading.Lock()
        self.tts_speech_token_dict = {}
        self.llm_end_dict = {}
        self.mel_overlap_dict = {}
        self.flow_cache_dict = {}
        self.hift_cache_dict = {}
        self.silent_tokens = []

    import numpy as np
    import threading

    model_module.CosyVoiceModel.__init__ = patched_init
    model_module.CosyVoice2Model.__init__ = patched_init


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    model_dir = Path(args.model_dir)
    reference_audio = Path(args.reference_audio)
    repo_dir = Path(args.repo_dir)
    temp_dir = Path(args.temp_dir)
    segments = load_segments(args)

    if not model_dir.exists():
        raise SystemExit(f"CosyVoice model directory not found: {model_dir}")
    if not reference_audio.exists():
        raise SystemExit(f"Reference audio not found: {reference_audio}")
    if not repo_dir.exists():
        raise SystemExit(f"CosyVoice repo directory not found: {repo_dir}")

    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    conda_bin = str(Path(sys.executable).resolve().parent)
    if conda_bin:
        os.environ["PATH"] = f"{conda_bin}:{os.environ.get('PATH', '')}"
    ffmpeg_bin = resolve_ffmpeg()
    ffmpeg_dir = str(Path(ffmpeg_bin).resolve().parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{ffmpeg_dir}:{os.environ.get('PATH', '')}"

    sys.path.insert(0, str(repo_dir))
    matcha_tts_dir = repo_dir / "third_party" / "Matcha-TTS"
    if matcha_tts_dir.exists():
        sys.path.insert(0, str(matcha_tts_dir))

    import torch

    import torchaudio
    import cosyvoice.cli.model as cosyvoice_model_module
    patch_cosyvoice_device(torch, cosyvoice_model_module, args.device)
    from cosyvoice.cli.cosyvoice import AutoModel

    temp_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    cleaned_reference = temp_dir / "reference_clean.wav"
    prompt_reference = temp_dir / "reference_prompt.wav"
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(reference_audio),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            str(cleaned_reference),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(cleaned_reference),
            "-t",
            "25",
            str(prompt_reference),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    prompt_text = args.prompt_text.strip() or transcribe_reference_audio(prompt_reference)
    cosyvoice = AutoModel(model_dir=str(model_dir))
    print(f"Using device: {args.device}")
    segment_outputs: list[Path] = []
    segment_dir = temp_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    for index, segment_text in enumerate(segments, start=1):
        generated = None
        for item in cosyvoice.inference_zero_shot(segment_text, prompt_text, str(prompt_reference), stream=False):
            generated = item
            break
        if generated is None:
            raise RuntimeError(f"CosyVoice 未返回第 {index} 段音频结果。")
        segment_output = segment_dir / f"segment_{index:03d}.wav"
        torchaudio.save(str(segment_output), generated["tts_speech"], cosyvoice.sample_rate)
        segment_outputs.append(segment_output)
        print(f"Generated segment {index}/{len(segments)} at {segment_output}")

    concatenate_wav_files(segment_outputs, output)
    print(f"Generated cloned voice at {output}")
    print(f"Prompt text: {prompt_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
