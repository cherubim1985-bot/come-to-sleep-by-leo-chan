#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import dedent


SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
DEFAULT_AFFIRMATIONS = [
    "Breathe in calm, breathe out tension.",
    "Let the body grow heavier with each breath.",
    "Release what is urgent and return to the present moment.",
    "Notice the air entering softly and leaving slowly.",
    "There is nothing to solve right now.",
    "Allow the shoulders, jaw, and hands to relax.",
    "You are safe to rest in this moment.",
    "Each exhale creates a little more space within.",
    "Let thoughts drift by like clouds crossing a wide sky.",
    "Quiet attention is enough.",
]


@dataclass
class AudioInfo:
    path: Path
    duration_seconds: float


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "meditation-video"


def format_seconds(total_seconds: float) -> str:
    seconds = max(0, int(round(total_seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


def parse_afinfo_duration(output: str) -> float:
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", output)
    if not match:
        raise RuntimeError("Could not parse duration from afinfo output.")
    return float(match.group(1))


def get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["afinfo", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_afinfo_duration(result.stdout)


def discover_audio_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES
    )


def pick_default_audio(audio_files: list[Path]) -> Path:
    if not audio_files:
        raise FileNotFoundError("No audio files were found in this folder.")
    mp3_files = [path for path in audio_files if path.suffix.lower() == ".mp3"]
    return mp3_files[0] if mp3_files else audio_files[0]


def split_chapters(duration_seconds: float, chapter_minutes: int) -> list[dict]:
    chapter_seconds = max(60, chapter_minutes * 60)
    chapter_count = max(1, math.ceil(duration_seconds / chapter_seconds))
    chapters = []
    for index in range(chapter_count):
        start = index * chapter_seconds
        end = min(duration_seconds, (index + 1) * chapter_seconds)
        chapters.append(
            {
                "index": index + 1,
                "title": f"Breath Cycle {index + 1}",
                "start": format_seconds(start),
                "end": format_seconds(end),
            }
        )
    return chapters


def build_subtitles(duration_seconds: float, affirmations: list[str], segment_seconds: int) -> str:
    cue_count = max(1, math.ceil(duration_seconds / max(15, segment_seconds)))
    lines = []
    for cue_index in range(cue_count):
        start = cue_index * segment_seconds
        end = min(duration_seconds, start + segment_seconds - 1)
        text = affirmations[cue_index % len(affirmations)]
        lines.extend(
            [
                str(cue_index + 1),
                f"{format_seconds(start).replace('.', ',')},000 --> {format_seconds(end).replace('.', ',')},000",
                text,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_svg(title: str, subtitle: str) -> str:
    return dedent(
        f"""\
        <svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
          <defs>
            <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#183a52"/>
              <stop offset="45%" stop-color="#285f70"/>
              <stop offset="100%" stop-color="#d8b46f"/>
            </linearGradient>
            <radialGradient id="glow" cx="50%" cy="45%" r="55%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.28"/>
              <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
            </radialGradient>
          </defs>
          <rect width="1920" height="1080" fill="url(#bg)"/>
          <rect width="1920" height="1080" fill="url(#glow)"/>
          <circle cx="960" cy="460" r="190" fill="none" stroke="#f7ead2" stroke-width="10" opacity="0.55"/>
          <circle cx="960" cy="460" r="250" fill="none" stroke="#f7ead2" stroke-width="4" opacity="0.35"/>
          <text x="960" y="770" text-anchor="middle" fill="#f9f3e7" font-size="92" font-family="Helvetica Neue, Arial, sans-serif" letter-spacing="3">
            {escape_xml(title)}
          </text>
          <text x="960" y="850" text-anchor="middle" fill="#fff8ea" font-size="42" font-family="Helvetica Neue, Arial, sans-serif" opacity="0.9">
            {escape_xml(subtitle)}
          </text>
        </svg>
        """
    )


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_render_script(project_dir: Path, audio_filename: str, title_svg_filename: str, srt_filename: str, output_filename: str) -> str:
    return dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        cd "{project_dir}"

        if ! command -v ffmpeg >/dev/null 2>&1; then
          echo "ffmpeg is not installed. Install ffmpeg first, then rerun this script."
          exit 1
        fi

        ffmpeg -y \\
          -loop 1 -i "{title_svg_filename}" \\
          -i "{audio_filename}" \\
          -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,subtitles={srt_filename}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00F9F3E7,OutlineColour=&H003C2B18,BorderStyle=3,Outline=1,Shadow=0,MarginV=70'" \\
          -c:v libx264 -tune stillimage -pix_fmt yuv420p -r 30 \\
          -c:a aac -b:a 192k -shortest \\
          "{output_filename}"

        echo "Rendered {output_filename}"
        """
    )


def build_import_notes(project_name: str, audio_filename: str, title_svg_filename: str, srt_filename: str) -> str:
    return dedent(
        f"""\
        Jianying import workflow for {project_name}

        1. Open Jianying and create a new 16:9 project.
        2. Import `{audio_filename}`, `{title_svg_filename}`, and `{srt_filename}` from this folder.
        3. Put the SVG on the main video track and stretch it to the full audio length.
        4. Put the audio on the music/voice track.
        5. Import the SRT captions if you want on-screen breathing prompts.
        6. Add your preferred ambient footage or stock background above the title card if desired.
        7. Export as 1080p H.264.

        Optional local render:
        - Run `./render_with_ffmpeg.sh` after ffmpeg is installed to export a ready-made MP4.
        """
    )


def create_project(root: Path, audio: AudioInfo, title: str, subtitle: str, chapter_minutes: int, segment_seconds: int) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    project_name = f"{slugify(title)}-{timestamp}"
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=False)

    copied_audio_path = project_dir / audio.path.name
    shutil.copy2(audio.path, copied_audio_path)

    chapters = split_chapters(audio.duration_seconds, chapter_minutes)
    subtitle_text = build_subtitles(audio.duration_seconds, DEFAULT_AFFIRMATIONS, segment_seconds)
    svg_text = build_svg(title, subtitle)
    srt_name = "breathing_prompts.srt"
    svg_name = "title_card.svg"
    output_name = f"{slugify(title)}.mp4"

    manifest = {
        "project_name": project_name,
        "title": title,
        "subtitle": subtitle,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "audio_file": audio.path.name,
        "duration_seconds": round(audio.duration_seconds, 3),
        "duration_hms": format_seconds(audio.duration_seconds),
        "chapters": chapters,
        "captions_file": srt_name,
        "title_card": svg_name,
        "render_output": output_name,
    }

    (project_dir / "project.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (project_dir / srt_name).write_text(subtitle_text, encoding="utf-8")
    (project_dir / svg_name).write_text(svg_text, encoding="utf-8")
    render_script_path = project_dir / "render_with_ffmpeg.sh"
    render_script_path.write_text(
        build_render_script(project_dir, audio.path.name, svg_name, srt_name, output_name),
        encoding="utf-8",
    )
    render_script_path.chmod(0o755)
    (project_dir / "JIANYING_IMPORT.md").write_text(
        build_import_notes(project_name, audio.path.name, svg_name, srt_name),
        encoding="utf-8",
    )
    return project_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a meditation video project package for Jianying."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Folder containing source audio files.",
    )
    parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="Specific audio filename to use.",
    )
    parser.add_argument(
        "--title",
        default="Morning Meditation",
        help="Displayed title for the meditation video.",
    )
    parser.add_argument(
        "--subtitle",
        default="Breathe, soften, and return to stillness",
        help="Displayed subtitle for the meditation video.",
    )
    parser.add_argument(
        "--chapter-minutes",
        type=int,
        default=5,
        help="Chapter length for the generated chapter list.",
    )
    parser.add_argument(
        "--segment-seconds",
        type=int,
        default=30,
        help="Subtitle cue length in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    audio_files = discover_audio_files(root)
    selected_audio = root / args.audio if args.audio else pick_default_audio(audio_files)
    if not selected_audio.exists():
        raise FileNotFoundError(f"Audio file not found: {selected_audio}")

    duration = get_audio_duration(selected_audio)
    audio_info = AudioInfo(path=selected_audio, duration_seconds=duration)
    project_dir = create_project(
        root=root,
        audio=audio_info,
        title=args.title,
        subtitle=args.subtitle,
        chapter_minutes=args.chapter_minutes,
        segment_seconds=args.segment_seconds,
    )

    print(f"Created project: {project_dir}")
    print(f"Audio duration: {format_seconds(duration)}")
    print(f"Import notes: {project_dir / 'JIANYING_IMPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
