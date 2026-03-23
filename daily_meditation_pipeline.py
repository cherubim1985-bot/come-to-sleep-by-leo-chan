#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import time
import wave
from array import array
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from textwrap import dedent
from urllib import error, parse, request


SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
DEFAULT_CONFIG = {
    "channel_name": "Daily Meditation",
    "duration_mode": "random_range",
    "default_duration_minutes": 20,
    "duration_min_minutes": 15,
    "duration_max_minutes": 30,
    "script_style": "human_spoken",
    "caption_segment_seconds": 12,
    "chapter_minutes": 2,
    "voice_clone": {
        "provider": "volcengine_v1",
        "voice_id": "replace-with-your-cloned-voice-id",
        "speaker_name": "My Clone Voice",
        "instructions": "温柔、稳定、慢速、贴近耳语但清晰。",
        "api_key": "",
        "model_id": "eleven_multilingual_v2",
        "output_format": "mp3_44100_128",
        "reference_audio": "1599 Ramblewood Ln 2.m4a",
        "reference_transcript": "",
        "cosyvoice": {
            "python_bin": "/tmp/cosyvoice-conda/bin/python",
            "script_path": "tools/cosyvoice_runner.py",
            "model_dir": "third_party/CosyVoice/pretrained_models/CosyVoice2-0.5B",
            "repo_dir": "third_party/CosyVoice",
            "temp_dir": "tmp/cosyvoice",
            "max_chunk_chars": 48,
        },
        "indextts": {
            "python_bin": "third_party/index-tts/.venv/bin/python",
            "script_path": "tools/indextts_runner.py",
            "model_dir": "third_party/index-tts/checkpoints",
            "config_path": "third_party/index-tts/checkpoints/config.yaml",
            "repo_dir": "third_party/index-tts",
            "temp_dir": "tmp/indextts",
            "max_chunk_chars": 56,
            "device": "cpu",
        },
        "say": {
            "voice": "Samantha",
            "rate": 115,
            "sample_rate": 24000,
            "channels": 1,
            "max_chunk_chars": 220,
        },
        "volcengine": {
            "app_id": "",
            "access_key": "",
            "secret_key": "",
            "speaker": "",
            "api_key": "",
            "cluster": "volcano_icl",
            "audio_format": "wav",
            "sample_rate": 24000,
            "speech_rate": 0,
            "loudness_rate": 0,
            "speed_ratio": 0.92,
            "max_chunk_chars": 170,
            "synth_url": "https://openspeech.bytedance.com/api/v1/tts",
            "request_timeout_seconds": 1800
        },
    },
    "music": {
        "strategy": "library",
        "avoid_recent_repeats": 7,
        "default_tags": ["meditation", "ambient", "slow", "instrumental"],
        "fallback_audio": "0208 (1).MP3",
    },
    "music_generation": {
        "provider": "manual",
        "endpoint": "https://example.com/generate-music",
        "method": "POST",
        "auth_header": "",
        "timeout_seconds": 120,
        "download_field": "audio_url",
        "base64_field": "audio_base64",
        "filename_field": "filename",
        "extra_payload": {},
    },
    "image_generation": {
        "provider": "manual",
        "api_key": "",
        "model": "gpt-image-1",
        "size": "1536x1024",
        "quality": "high",
        "background": "opaque",
        "output_format": "png",
    },
    "publishing": {
        "media_base_url": "",
        "copy_media_to_deploy": True,
    },
}
DEFAULT_THEMES = [
    {
        "name": "清晨安定",
        "subtitle": "在一天开始前，让呼吸先安静下来",
        "music_tags": ["morning", "warm", "light", "peaceful"],
        "practice_preferences": ["道家松静", "内观呼吸", "行禅式觉察", "盒式呼吸"],
        "image_keywords": ["sunrise lake", "mist", "soft gold", "still water"],
        "opening": "欢迎来到今天的冥想。请找一个舒服的位置坐下，轻轻闭上眼睛。",
        "body_focus": "把注意力带回呼吸，感受吸气时胸口微微打开，呼气时身体慢慢放松。",
        "closing": "当你准备好的时候，带着这一份安定，慢慢回到今天的生活里。",
    },
    {
        "name": "深度放松",
        "subtitle": "让紧绷的身体一点一点松开",
        "music_tags": ["night", "deep", "floating", "soft"],
        "practice_preferences": ["身体扫描", "瑜伽尼德拉", "视觉观想", "4-7-8 呼吸"],
        "image_keywords": ["moonlit sea", "deep blue", "slow waves", "minimal"],
        "opening": "这一刻，不需要完成任何事。你只需要允许自己停下来。",
        "body_focus": "从额头到肩膀，从胸口到腹部，再到双腿和双脚，依次松开每一处紧张。",
        "closing": "把松弛的感觉记住，让它陪你进入接下来的夜晚或休息时间。",
    },
    {
        "name": "睡前释放",
        "subtitle": "把白天的杂念温柔放下",
        "music_tags": ["sleep", "night", "slow", "airy"],
        "practice_preferences": ["瑜伽尼德拉", "慈心观", "视觉观想", "4-7-8 呼吸"],
        "image_keywords": ["night sky", "stars", "mountain silhouette", "quiet"],
        "opening": "如果你正在为睡眠做准备，请让身体更舒适一些，慢慢把注意力收回来。",
        "body_focus": "每一次呼气，都想象把今天的疲惫、压力和思绪轻轻放下。",
        "closing": "愿你在接下来的时间里，更轻、更稳，也更容易进入睡眠。",
    },
    {
        "name": "情绪舒缓",
        "subtitle": "给情绪一点空间，也给自己一点温柔",
        "music_tags": ["healing", "forest", "gentle", "emotional"],
        "practice_preferences": ["慈心观", "身体扫描", "声音锚定", "视觉观想"],
        "image_keywords": ["forest light", "green", "gentle haze", "peaceful path"],
        "opening": "此刻不需要压抑情绪，也不需要立刻改变它，只是先陪伴自己。",
        "body_focus": "感受情绪像潮水一样来去，而你只是在呼吸里稳稳地停留。",
        "closing": "带着更柔软的心，继续今天剩下的路程。",
    },
    {
        "name": "专注回归",
        "subtitle": "把分散的注意力重新带回当下",
        "music_tags": ["focus", "minimal", "steady", "clean"],
        "practice_preferences": ["内观呼吸", "禅宗观照", "盒式呼吸", "数息法"],
        "image_keywords": ["zen room", "warm light", "clean composition", "calm"],
        "opening": "如果你的思绪有些散乱，没有关系，我们现在一起把它轻轻带回来。",
        "body_focus": "关注空气经过鼻尖的细微触感，把每一次呼吸当作回到当下的锚点。",
        "closing": "愿你带着更清楚、更稳定的专注感，进入接下来的工作与生活。",
    },
]
MEDITATION_TRADITIONS = [
    {
        "name": "内观呼吸",
        "origin": "南传观息",
        "tags": ["breath", "focus", "clarity"],
        "opening_lines": [
            "先把注意力轻轻放在鼻尖，观察空气进入与离开的细微触感。",
            "不需要控制呼吸，只是如实地看见每一次吸气与呼气。",
        ],
        "practice_lines": [
            "当呼吸变得细一点、轻一点，也只是安静地知道它正在发生。",
            "如果注意力跑远了，就像把一片叶子放回水面一样，把觉察带回呼吸。",
        ],
        "integration_lines": [
            "让清明的观察力留在心里，带着它回到接下来的生活节奏中。",
        ],
    },
    {
        "name": "身体扫描",
        "origin": "正念减压",
        "tags": ["body", "relax", "healing"],
        "opening_lines": [
            "把觉察从头顶缓缓带到额头、眼周、下颌，感受每一处是否愿意再放松一点。",
            "让注意力像一束温柔的光，缓慢地照见身体的每一个区域。",
        ],
        "practice_lines": [
            "从肩膀到手臂、从胸口到腹部、从骨盆到双腿，逐一停留，逐一松开。",
            "不必急着改变感受，只是先认识它，再允许它慢慢软下来。",
        ],
        "integration_lines": [
            "记住这种从身体内部展开的松弛感，它可以成为你每天的安稳基地。",
        ],
    },
    {
        "name": "慈心观",
        "origin": "慈悲禅修",
        "tags": ["heart", "emotion", "sleep", "healing"],
        "opening_lines": [
            "把注意力轻轻带到心口，像把双手放在温暖的地方一样，停留在那里。",
            "在心里给自己一句简单而善意的祝福，让内在慢慢柔软下来。",
        ],
        "practice_lines": [
            "你可以默念：愿我平安，愿我安稳，愿我今夜得到真正的休息。",
            "如果愿意，也把这份温柔送给今天遇见的人，让心慢慢从紧绷回到柔和。",
        ],
        "integration_lines": [
            "让善意留在胸口，像一盏低低发亮的灯，陪你继续往前走。",
        ],
    },
    {
        "name": "禅宗观照",
        "origin": "东亚禅修",
        "tags": ["stillness", "focus", "clarity"],
        "opening_lines": [
            "这一刻不急着解释任何体验，只是安静地坐着，安静地知道。",
            "让身体正直而不僵硬，让心保持简单，不追逐，也不抗拒。",
        ],
        "practice_lines": [
            "念头来了，就看见它；念头走了，也看见它。你只是稳稳坐在觉知里。",
            "把每一次分心，都当作再次醒来的机会，而不是失败。",
        ],
        "integration_lines": [
            "把这份简单清醒带走，让你在纷乱中也能保留一点静定。",
        ],
    },
    {
        "name": "瑜伽尼德拉",
        "origin": "瑜伽休息术",
        "tags": ["sleep", "deep", "body", "night"],
        "opening_lines": [
            "让身体找到一种被地面承托的感觉，像完全可以放心沉下去一样。",
            "提醒自己，此刻不需要努力，你正在进入一种有觉知的深度休息。",
        ],
        "practice_lines": [
            "让意识在身体各处轻轻移动，每到一处，只要感受，然后放松。",
            "随着呼气，想象整个人一层一层地下沉，进入更安静、更柔软的休息状态。",
        ],
        "integration_lines": [
            "把这份深休息留给自己，让夜晚真正成为恢复与滋养的时间。",
        ],
    },
    {
        "name": "道家松静",
        "origin": "道家养生观",
        "tags": ["flow", "morning", "healing", "body"],
        "opening_lines": [
            "感受呼吸像水一样自然流动，不争不抢，只是顺势而行。",
            "让肩松、胸松、腹松，像身体里有一股气息慢慢归于平和。",
        ],
        "practice_lines": [
            "每一次吸气，像把清新的气带入身体；每一次呼气，像把浊重慢慢送走。",
            "让心沉下来，让气沉下来，让整个身体回到松、静、柔、稳的状态。",
        ],
        "integration_lines": [
            "把这种松而不散、静而不冷的感觉，带进今天的行动里。",
        ],
    },
    {
        "name": "行禅式觉察",
        "origin": "行禅与日常正念",
        "tags": ["focus", "daily", "clarity", "emotion"],
        "opening_lines": [
            "虽然此刻你可能是静坐着，但我们可以练习一种像走路时那样清醒的觉察。",
            "把这一刻当作生活的一部分，而不是与生活分开的片刻。",
        ],
        "practice_lines": [
            "去感觉身体与座椅、双脚与地面、呼吸与胸腹之间的真实联系。",
            "让觉察不仅停留在呼吸，也停留在当下这一整个活生生的片刻。",
        ],
        "integration_lines": [
            "当冥想结束后，把同样的觉察带进走路、说话、工作和休息里。",
        ],
    },
    {
        "name": "视觉观想",
        "origin": "观想放松",
        "tags": ["imagery", "sleep", "healing", "emotional"],
        "opening_lines": [
            "想象自己正置身一片宁静的自然空间，四周安全、开阔，而且柔和。",
            "让心里出现一个安静的画面，也许是湖面、山谷、星空，或者清晨的雾气。",
        ],
        "practice_lines": [
            "随着呼吸，想象那片景象变得更宽、更静，也让你的身体跟着一起放松。",
            "把压在心上的内容，轻轻交给这片空间，让它帮你承接与稀释。",
        ],
        "integration_lines": [
            "把这个内在风景记下来，以后任何需要安定的时刻，你都能重新回到这里。",
        ],
    },
    {
        "name": "盒式呼吸",
        "origin": "现代呼吸训练",
        "tags": ["focus", "breath", "clarity", "daily"],
        "opening_lines": [
            "现在我们把呼吸整理成稳定的节奏，让心和身体先回到同一个拍子。",
            "想象呼吸像一个安静的方形，每一边都均匀、清楚、可被感知。",
        ],
        "practice_lines": [
            "吸气四拍，停留四拍，呼气四拍，停留四拍，让节律帮助注意力收束。",
            "当你能够跟上这个节奏时，心会变得更集中，也更不容易被杂念拉走。",
        ],
        "integration_lines": [
            "以后当你需要快速稳定自己时，也可以用这一组呼吸重新回到中心。",
        ],
    },
    {
        "name": "4-7-8 呼吸",
        "origin": "放松呼吸法",
        "tags": ["sleep", "night", "relax", "breath"],
        "opening_lines": [
            "接下来我们用一种更偏放松的呼吸比例，让神经系统更快进入安定状态。",
            "不要勉强自己憋气，只要在舒服的范围内轻轻延长呼气就可以。",
        ],
        "practice_lines": [
            "吸气四拍，停留七拍，呼气八拍，如果节奏太长，就温柔地缩短但保留呼长于吸。",
            "让每一次更长的呼气都像在告诉身体，现在可以休息了。",
        ],
        "integration_lines": [
            "把这种长呼气带来的松弛感保留下来，它很适合睡前和压力高的时候使用。",
        ],
    },
    {
        "name": "数息法",
        "origin": "东亚数息观",
        "tags": ["focus", "breath", "clarity"],
        "opening_lines": [
            "现在给呼吸一个简单的锚点，我们用数字帮助注意力稳下来。",
            "每一次呼吸只做一件事，就是知道自己正呼到第几个数。",
        ],
        "practice_lines": [
            "从一数到十，吸气时知道在吸，呼气时轻轻数一下，然后再从一重新开始。",
            "如果中途忘了数到哪里，不需要懊恼，只要重新从一开始，这本身就是练习。",
        ],
        "integration_lines": [
            "数息的力量在于简单，它能在很短时间里把散乱重新整理成秩序。",
        ],
    },
    {
        "name": "声音锚定",
        "origin": "声音正念",
        "tags": ["emotion", "healing", "daily", "clarity"],
        "opening_lines": [
            "除了呼吸之外，也把周围的声音当作当下的一部分，轻轻纳入觉察里。",
            "不需要挑选声音，只是听见近处、远处、持续的、偶尔出现的所有声音。",
        ],
        "practice_lines": [
            "当有声音传来，不给它贴标签，只说一声：听见了，然后回到身体。",
            "让声音成为提醒你醒着、在场、此刻没有离开的提示，而不是干扰。",
        ],
        "integration_lines": [
            "以后在嘈杂环境里，你也可以用声音来练习稳定，而不是非要等完全安静才开始。",
        ],
    },
    {
        "name": "咒音专注",
        "origin": "mantra 声音专注",
        "tags": ["focus", "heart", "stillness", "night"],
        "opening_lines": [
            "现在在心里给自己一个非常简单的声音或词语，让它成为觉察的落点。",
            "这个声音不需要神秘，它只是帮助心停留的节律，比如一声轻轻的“安”或“静”。",
        ],
        "practice_lines": [
            "随着呼吸在心里重复这个声音，让心不要四处伸展，而是慢慢回到同一个中心。",
            "当念头插进来时，不和它争辩，只要回到那一个轻柔重复的声音。",
        ],
        "integration_lines": [
            "声音会留下余韵，让你在离开冥想之后，心里仍有一条细细稳定的线。",
        ],
    },
]


@dataclass
class AudioTrack:
    path: Path
    duration_seconds: float
    tags: list[str]
    selection_reason: str


@dataclass
class GeneratedMusicResult:
    provider: str
    status: str
    prompt: str
    request_payload: dict
    output_file: str | None
    source_url: str | None
    message: str


@dataclass
class GeneratedAssetResult:
    provider: str
    status: str
    request_payload: dict
    output_file: str | None
    source_url: str | None
    message: str


def slugify(text: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value.lower() or "daily-meditation"


def load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def merge_dict(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class ReadTimeoutError(TimeoutError):
    pass


def _raise_read_timeout(signum, frame):
    raise ReadTimeoutError("Timed out while reading JSON file.")


def load_json_with_timeout(path: Path, fallback, timeout_seconds: int = 2):
    if not path.exists():
        return fallback

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _raise_read_timeout)
    signal.alarm(timeout_seconds)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ReadTimeoutError):
        return fallback
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def ensure_workspace(root: Path) -> None:
    for name in ["config", "assets/music", "output", "state"]:
        (root / name).mkdir(parents=True, exist_ok=True)


def write_if_missing(path: Path, payload: str) -> None:
    if not path.exists():
        path.write_text(payload, encoding="utf-8")


def bootstrap_files(root: Path) -> None:
    ensure_workspace(root)
    write_if_missing(
        root / "config" / "project_config.json",
        json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n",
    )
    write_if_missing(
        root / "config" / "theme_library.json",
        json.dumps(DEFAULT_THEMES, ensure_ascii=False, indent=2) + "\n",
    )
    write_if_missing(
        root / "assets" / "music" / "README.md",
        dedent(
            """\
            把可循环使用的冥想背景音乐放在这个目录。

            支持格式：mp3 / wav / m4a / aac / flac
            建议命名：calm-01.mp3, sleep-02.mp3, ocean-soft.mp3
            
            可选：维护一个 music_library.json 来给每首音乐打标签，例如：
            [
              {"filename": "sleep-02.mp3", "tags": ["sleep", "night", "airy"]},
              {"filename": "focus-01.mp3", "tags": ["focus", "minimal", "steady"]}
            ]
            """
        ),
    )
    write_if_missing(
        root / "assets" / "music" / "music_library.json",
        "[]\n",
    )
    write_if_missing(
        root / "state" / "README.md",
        "这里保存每日生成状态，用于避免主题重复。\n",
    )


def format_hms(total_seconds: float) -> str:
    rounded = max(0, int(round(total_seconds)))
    hours, remainder = divmod(rounded, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def choose_duration_minutes(config: dict, target_date: date, theme: dict) -> int:
    mode = str(config.get("duration_mode", "fixed")).strip().lower()
    default_minutes = max(1, int(config.get("default_duration_minutes", 20)))
    if mode != "random_range":
        return default_minutes

    minimum = max(1, int(config.get("duration_min_minutes", 15)))
    maximum = max(minimum, int(config.get("duration_max_minutes", 30)))
    seed = f"{target_date.isoformat()}::{theme.get('name', '')}::{config.get('channel_name', '')}"
    value = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    return minimum + (value % (maximum - minimum + 1))


def pick_deterministic_items(items: list[dict], count: int, seed: str) -> list[dict]:
    scored = []
    for item in items:
        digest = hashlib.sha256(f"{seed}::{item['name']}".encode("utf-8")).hexdigest()
        scored.append((digest, item))
    scored.sort(key=lambda item: item[0])
    return [item for _, item in scored[:count]]


def choose_meditation_traditions(theme: dict, duration_minutes: int) -> list[dict]:
    theme_tags = set(normalize_tags(theme.get("music_tags", [])))
    preferred = set(str(item).strip() for item in theme.get("practice_preferences", []))
    desired_count = 2 if duration_minutes < 22 else 3
    scored = []
    for tradition in MEDITATION_TRADITIONS:
        overlap = len(theme_tags & set(tradition["tags"]))
        preference_bonus = 3 if tradition["name"] in preferred else 0
        digest = hashlib.sha256(f"{theme.get('name','')}::{tradition['name']}".encode("utf-8")).hexdigest()
        scored.append((overlap + preference_bonus, overlap, digest, tradition))
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    selected = [item[3] for item in scored[:desired_count]]
    if len(selected) < desired_count:
        selected.extend(pick_deterministic_items(MEDITATION_TRADITIONS, desired_count - len(selected), theme.get("name", "")))
    return selected[:desired_count]


def choose_spoken_variant(options: list[str], seed: str) -> str:
    return pick_deterministic_items(
        [{"name": option, "line": option} for option in options],
        1,
        seed,
    )[0]["line"]


def compact_blank_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    for line in lines:
        text = line.strip()
        if not text:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(text)
    if cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned)


def parse_afinfo_duration(output: str) -> float:
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", output)
    if not match:
        raise RuntimeError("无法从 afinfo 输出中解析音频时长。")
    return float(match.group(1))


def get_audio_duration(path: Path) -> float:
    result = subprocess.run(["afinfo", str(path)], check=True, capture_output=True, text=True)
    return parse_afinfo_duration(result.stdout)


def safe_get_audio_duration(path: Path) -> float | None:
    try:
        return get_audio_duration(path)
    except Exception:
        return None


def discover_audio_tracks(directory: Path) -> list[Path]:
    return sorted(
        path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES
    )


def normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    return [str(tag).strip().lower() for tag in tags if str(tag).strip()]


def split_voice_text(script_text: str, max_chunk_chars: int) -> list[str]:
    chunks: list[str] = []
    max_chunk_chars = max(20, int(max_chunk_chars))
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", script_text) if item.strip()]
    buffer = ""
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", "", paragraph)
        sentences = [item.strip() for item in re.split(r"(?<=[。！？!?])", normalized) if item.strip()]
        for sentence in sentences:
            if len(sentence) > max_chunk_chars:
                if buffer:
                    chunks.append(buffer)
                    buffer = ""
                parts = [item.strip() for item in re.split(r"[，、,；;]", sentence) if item.strip()]
                partial = ""
                for part in parts:
                    candidate = f"{partial}，{part}" if partial else part
                    if partial and len(candidate) > max_chunk_chars:
                        chunks.append(partial)
                        partial = part
                    else:
                        partial = candidate
                if partial:
                    chunks.append(partial)
                continue
            candidate = f"{buffer}{sentence}" if buffer else sentence
            if buffer and len(candidate) > max_chunk_chars:
                chunks.append(buffer)
                buffer = sentence
            else:
                buffer = candidate
        if buffer:
            chunks.append(buffer)
            buffer = ""
    return chunks


def build_spoken_blocks(lines_with_pause: list[tuple[str, int | None]]) -> list[dict]:
    blocks: list[dict] = []
    for text, pause_after_ms in lines_with_pause:
        cleaned = str(text).strip()
        if not cleaned:
            continue
        blocks.append(
            {
                "text": cleaned,
                "pause_after_ms": max(0, int(pause_after_ms or 0)),
            }
        )
    return blocks


def explode_spoken_blocks(blocks: list[dict], max_chunk_chars: int) -> list[dict]:
    expanded: list[dict] = []
    for block in blocks:
        text = str(block.get("text", "")).strip()
        pause_after_ms = max(0, int(block.get("pause_after_ms", 0)))
        if not text:
            continue
        parts = split_voice_text(text, max_chunk_chars)
        if len(parts) <= 1:
            expanded.append({"text": text, "pause_after_ms": pause_after_ms})
            continue
        for index, part in enumerate(parts):
            expanded.append(
                {
                    "text": part,
                    "pause_after_ms": pause_after_ms if index == len(parts) - 1 else 500,
                }
            )
    return expanded


def concatenate_wav_files(source_files: list[Path], output_path: Path) -> None:
    if not source_files:
        raise ValueError("No wav files to concatenate.")
    with wave.open(str(source_files[0]), "rb") as first:
        params = first.getparams()
        frames = [first.readframes(first.getnframes())]
    for source_file in source_files[1:]:
        with wave.open(str(source_file), "rb") as current:
            current_params = current.getparams()
            if (
                current_params.nchannels != params.nchannels
                or current_params.sampwidth != params.sampwidth
                or current_params.framerate != params.framerate
                or current_params.comptype != params.comptype
            ):
                raise ValueError(f"WAV parameters do not match for concatenation: {source_file}")
            frames.append(current.readframes(current.getnframes()))
    with wave.open(str(output_path), "wb") as target:
        target.setparams(params)
        for frame_chunk in frames:
            target.writeframes(frame_chunk)


def write_silence_wav(output_path: Path, duration_ms: int, nchannels: int = 1, sampwidth: int = 2, framerate: int = 24000) -> None:
    frame_count = max(1, int(framerate * max(0, duration_ms) / 1000))
    silence_frame = b"\x00" * sampwidth * nchannels
    with wave.open(str(output_path), "wb") as target:
        target.setnchannels(nchannels)
        target.setsampwidth(sampwidth)
        target.setframerate(framerate)
        target.writeframes(silence_frame * frame_count)


def copy_generated_segments(temp_segment_dir: Path, destination_dir: Path) -> list[Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source_file in sorted(temp_segment_dir.glob("segment_*.wav")):
        target_file = destination_dir / source_file.name
        shutil.copy2(source_file, target_file)
        copied.append(target_file)
    return copied


def load_music_library(root: Path) -> dict[str, list[str]]:
    library_path = root / "assets" / "music" / "music_library.json"
    entries = load_json(library_path, [])
    mapping: dict[str, list[str]] = {}
    for entry in entries:
        filename = str(entry.get("filename", "")).strip()
        if not filename:
            continue
        mapping[filename] = normalize_tags(entry.get("tags", []))
    return mapping


def read_generation_log(root: Path) -> list[dict]:
    return load_json(root / "state" / "generation_log.json", [])


def recent_music_filenames(root: Path, limit: int) -> list[str]:
    history = read_generation_log(root)
    filenames = []
    for item in reversed(history):
        music_filename = item.get("music_filename")
        if music_filename:
            filenames.append(music_filename)
        if len(filenames) >= limit:
            break
    return filenames


def choose_theme(themes: list[dict], target_date: date) -> dict:
    if not themes:
        raise ValueError("主题库为空。")
    digest = hashlib.sha256(target_date.isoformat().encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(themes)
    theme = dict(themes[index])
    if "music_tags" not in theme:
        fallback = next((item for item in DEFAULT_THEMES if item["name"] == theme.get("name")), {})
        theme["music_tags"] = fallback.get("music_tags", [])
    if "practice_preferences" not in theme:
        theme["practice_preferences"] = []
    if "category" not in theme:
        theme["category"] = "Sleep Meditation"
    return theme


def choose_theme_by_name(themes: list[dict], theme_name: str) -> dict:
    desired = theme_name.strip()
    for theme in themes:
        if str(theme.get("name", "")).strip() == desired:
            selected = dict(theme)
            if "music_tags" not in selected:
                selected["music_tags"] = []
            if "practice_preferences" not in selected:
                selected["practice_preferences"] = []
            if "category" not in selected:
                selected["category"] = "Sleep Meditation"
            return selected
    raise ValueError(f"Theme not found: {theme_name}")


def score_track(tags: list[str], desired_tags: list[str], recent_files: list[str], filename: str) -> tuple[int, int]:
    matched = len(set(tags) & set(desired_tags))
    repeated_penalty = -100 if filename in recent_files else 0
    return (matched, repeated_penalty)


def choose_music(root: Path, config: dict, theme: dict, target_date: date) -> AudioTrack | None:
    music_config = config.get("music", {})
    if str(music_config.get("strategy", "library")).strip().lower() in {"none", "off", "disabled", "voice_only"}:
        return None
    library_tracks = discover_audio_tracks(root / "assets" / "music")
    desired_tags = normalize_tags(music_config.get("default_tags", [])) + normalize_tags(theme.get("music_tags", []))
    recent_files = recent_music_filenames(root, int(music_config.get("avoid_recent_repeats", 7)))
    tag_mapping = load_music_library(root)
    if library_tracks:
        scored_tracks = []
        for track in library_tracks:
            tags = tag_mapping.get(track.name, normalize_tags(re.split(r"[-_\s]+", track.stem)))
            score = score_track(tags, desired_tags, recent_files, track.name)
            seed = hashlib.sha256(f"{target_date.isoformat()}::{track.name}".encode("utf-8")).hexdigest()
            scored_tracks.append((score, seed, track, tags))
        scored_tracks.sort(key=lambda item: (item[0][0], item[0][1], item[1]), reverse=True)
        best_score, _, selected, tags = scored_tracks[0]
        reason = f"matched_tags={best_score[0]}, repeated_recently={'yes' if selected.name in recent_files else 'no'}"
        return AudioTrack(
            path=selected,
            duration_seconds=get_audio_duration(selected),
            tags=tags,
            selection_reason=reason,
        )

    fallback_name = music_config.get("fallback_audio")
    if fallback_name:
        fallback_path = root / fallback_name
        if fallback_path.exists():
            fallback_tags = normalize_tags(theme.get("music_tags", [])) or normalize_tags(music_config.get("default_tags", []))
            return AudioTrack(
                path=fallback_path,
                duration_seconds=get_audio_duration(fallback_path),
                tags=fallback_tags,
                selection_reason="fallback_audio",
            )
    return None


def build_meditation_script(theme: dict, duration_minutes: int, target_date: date | None = None, script_style: str = "human_spoken") -> dict:
    if str(theme.get("language", "")).strip().lower() == "en":
        return build_english_sleep_script(theme, duration_minutes, target_date, script_style)

    traditions = choose_meditation_traditions(theme, duration_minutes)
    seed = f"{(target_date.isoformat() if target_date else 'na')}::{theme['name']}::{duration_minutes}"
    breath_cycles = max(5, duration_minutes // 2)
    tradition_openings = [
        choose_spoken_variant(tradition["opening_lines"], f"{seed}::opening::{tradition['name']}")
        for tradition in traditions
    ]
    tradition_practices = [
        choose_spoken_variant(tradition["practice_lines"], f"{seed}::practice::{tradition['name']}")
        for tradition in traditions
    ]
    tradition_integrations = [
        choose_spoken_variant(tradition["integration_lines"], f"{seed}::integration::{tradition['name']}")
        for tradition in traditions
    ]

    if script_style.strip().lower() == "human_spoken":
        intro_pause = 3600
        settle_pause = 5200
        breath_pause = 6500
        reflection_pause = 4200
        transition_pause = 3000
        closing_pause = 7000
        breath_invites = [
            "慢慢地，把注意力带到呼吸上。",
            "现在不需要把呼吸做得很完美，只要让它比刚才更柔和一点就可以。",
            "继续留在呼吸里，让每一口气都带着一点放松往身体里走。",
            "如果你愿意，就让呼吸再慢下来一点点，让身体知道，今晚真的可以休息了。",
        ]
        breath_patterns = [
            "轻轻吸气，心里数四拍。停留一下，然后慢慢呼气，呼到六拍，或者更长一点也可以。",
            "如果你愿意，接下来也可以试试四七八的节奏。吸气四拍，停留七拍，呼气八拍。不需要勉强，舒服最重要。",
            "把呼吸放回自然，只是观察身体最明显的起伏，也许是在鼻尖，也许是在胸口，也许是在腹部。",
            "如果想让注意力更稳一点，就在每一次呼气时轻轻数数，从一到十，再温柔地回到一。",
        ]
        recovery_lines = [
            "如果这个时候有念头冒出来，也没关系。你不需要责怪自己，只要再一次轻轻回到呼吸上。",
            "如果情绪在这个时候浮上来，也不需要急着推开它。先看见它，然后再回到身体和呼吸。",
            "每一次回到当下，都不是失败，而是在慢慢训练一种更稳定的内在节律。",
        ]
        grounding_lines = [
            "去感觉自己正被下面的支撑轻轻托住，头部被托住，肩膀被托住，后背和双腿也都被托住。",
            "让身体把重量一点一点交出去，你不需要再做什么，身体自然会知道怎么休息。",
            "随着每一次呼气，想象自己正缓缓地下沉，不是掉下去，而是沉进一种安静、柔软、很安全的休息里。",
        ]
        heart_lines = [
            "把注意力轻轻带到心口的位置，不用做什么，只是感觉那里。",
            "如果你愿意，可以在心里对自己说一句很简单的话。愿我今夜安稳。愿我慢慢放下。愿我得到真正的休息。",
            "让这份善意留在心里，不需要很强烈，只要像一盏低低发亮的灯，安静地亮着就够了。",
        ]
        lines_with_pause: list[tuple[str, int]] = [
            (theme["opening"].replace("请", "就").replace("，轻轻闭上眼睛。", "，轻轻把眼睛闭上。"), intro_pause),
            ("不用急着进入状态，也不用要求自己马上安静下来。", settle_pause),
            ("先只是感觉一下，此刻你是安全的，你正在被这一小段属于自己的时间温柔地承托着。", settle_pause),
            (theme["body_focus"], breath_pause),
            (breath_invites[0], transition_pause),
            (breath_patterns[0], breath_pause),
            (tradition_openings[0], reflection_pause),
            (tradition_practices[0], breath_pause),
            (recovery_lines[0], reflection_pause),
        ]
        for index in range(breath_cycles):
            lines_with_pause.append((breath_invites[(index + 1) % len(breath_invites)], transition_pause))
            lines_with_pause.append((breath_patterns[index % len(breath_patterns)], breath_pause))
            lines_with_pause.append((recovery_lines[index % len(recovery_lines)], reflection_pause))
            if index == max(1, breath_cycles // 3):
                for item in grounding_lines:
                    lines_with_pause.append((item, settle_pause))
            if index < len(tradition_practices):
                lines_with_pause.append((tradition_practices[index], breath_pause))
            elif index < breath_cycles - 2:
                lines_with_pause.append((tradition_integrations[index % len(tradition_integrations)], reflection_pause))
            if index == max(2, (breath_cycles * 2) // 3):
                for item in heart_lines:
                    lines_with_pause.append((item, settle_pause))
        lines_with_pause.extend(
            [
                ("然后再一次回到呼吸。吸气，轻一点。呼气，长一点。", breath_pause),
                ("如果你的意识开始慢慢模糊下来，就顺着它走。如果你还清醒，也没有关系，就继续留在这份安静里。", settle_pause),
                ("让呼吸继续变慢，让身体继续变软，让心继续变安静。", closing_pause),
                ("在这段冥想快要结束的时候，不需要立刻睁眼，也不需要马上起身。", closing_pause),
                ("只要记住这种感觉。那种胸口慢慢安静下来、身体慢慢沉下来、呼吸慢慢细下来的感觉。", settle_pause),
                (theme["closing"], closing_pause),
            ]
        )
        for item in tradition_integrations[:2]:
            lines_with_pause.append((item, settle_pause))
        spoken_blocks = build_spoken_blocks(lines_with_pause)
        guidance = compact_blank_lines([block["text"] for block in spoken_blocks])
    else:
        rotating_breaths = [
            "现在我们做一轮均匀呼吸。吸气四拍，停留一拍，呼气六拍，让神经系统慢慢安静。",
            "接下来把呼气稍微放长。吸气四拍，呼气六到八拍，让身体更愿意松开。",
            "这一轮只需要自然呼吸，同时观察身体最明显的起伏点，可能是鼻尖、胸口或腹部。",
            "把这一轮呼吸变成无声的数息练习，从一数到十，再轻轻回到一。",
        ]
        return_lines = [
            "如果念头出现，不需要批评自己，只要温柔地把注意力带回此刻。",
            "如果情绪浮上来，也不用压下去，先让它被看见，然后继续回到呼吸和身体。",
            "每一次回到当下，都是在训练内在的稳定，而不是在追求完美。",
        ]
        middle_lines = []
        for index in range(breath_cycles):
            middle_lines.append(rotating_breaths[index % len(rotating_breaths)])
            middle_lines.append(return_lines[index % len(return_lines)])
            if index < len(tradition_practices):
                middle_lines.append(tradition_practices[index])
        spoken_blocks = build_spoken_blocks(
            [
                (theme["opening"], 3000),
                ("先让自己安顿下来，不急着进入技巧，只是确认此刻你是安全的、被支持的。", 4200),
                (theme["body_focus"], 5000),
                *[(item, 3800) for item in tradition_openings],
                *[(item, 4200) for item in middle_lines],
                ("把注意力带回心口，感受身体内部已经慢慢安静下来。", 5000),
                (theme["closing"], 6000),
                *[(item, 4200) for item in tradition_integrations[:2]],
            ]
        )
        guidance = compact_blank_lines([block["text"] for block in spoken_blocks])
    return {
        "title": theme["name"],
        "subtitle": theme["subtitle"],
        "duration_minutes": duration_minutes,
        "script_style": script_style,
        "traditions": [{"name": item["name"], "origin": item["origin"]} for item in traditions],
        "full_text": guidance,
        "spoken_blocks": spoken_blocks,
    }


def build_english_sleep_script(
    theme: dict,
    duration_minutes: int,
    target_date: date | None = None,
    script_style: str = "human_spoken",
) -> dict:
    seed = f"{(target_date.isoformat() if target_date else 'na')}::{theme['name']}::{duration_minutes}::english"
    drift_cycles = max(8, duration_minutes // 2)
    opening_variants = [
        "You do not have to do this well tonight. You only have to let yourself be here.",
        "If the day is still clinging to you a little, that is all right. We do not have to pull it away all at once.",
        "Let this be quieter than a practice and more like company at the end of a long day.",
        "For these next few minutes, you can stop holding yourself up in all the usual ways.",
    ]
    settling_lines = [
        "Feel the surface beneath you taking the weight of your head, your shoulders, your back, your hips, and your legs.",
        "The tiny muscles around the eyes can soften now. The jaw can soften. The tongue can rest.",
        "Let the throat be easy. Let the chest stop bracing. Let the belly loosen the way it does when you finally know you are alone and safe.",
        "There is nothing you need to prepare before rest is allowed to begin.",
    ]
    breath_lines = [
        "Take one unhurried breath in, and let the exhale be a little longer, as though the body is putting something down.",
        "You do not need a technique to impress anyone here. A soft breath is enough. A longer exhale is enough.",
        "Let the next breath arrive on its own. You are not managing it. You are only meeting it.",
        "If it helps, think of the exhale as the part of the breath that knows the way home.",
        "Each time the breath leaves, let the shoulders drop by the smallest amount, like a room dimming at night.",
        "Nothing has to become perfect. It only has to become slightly easier than it was a moment ago.",
    ]
    reassurance_lines = [
        "If the mind is still talking, let it talk farther away. You do not need to answer it.",
        "If some feeling is still awake inside you, let it be there without turning it into a problem.",
        "A restless night can still become a gentle one.",
        "You are allowed to be tired without needing to explain why.",
        "Nothing in you has to be solved before sleep can come closer.",
        "Even now, the body may be unwinding in ways you do not have to notice to benefit from.",
    ]
    imagery_lines = [
        "Imagine the room growing softer around you, as though the night is folding a blanket over every sharp edge.",
        "Picture your thoughts drifting like distant lights seen from far away. They can remain there without reaching you.",
        "Let the body feel heavier in the kindest way, not sinking, only being received.",
        "It may help to imagine you are floating just below the surface of still water, held quietly from all sides.",
        "The night does not need anything from you now except your willingness to be carried a little.",
    ]
    companion_lines = [
        "You do not have to stay ahead of the night. You can let the night catch up to you.",
        "If sleep comes before this recording ends, you do not need to keep me with you. You can leave my voice behind.",
        "And if you are not asleep yet, that does not mean this is failing. Rest often arrives in layers.",
        "Sometimes the first gift of the night is not sleep itself, but the moment the body stops arguing with wakefulness.",
        "Let this be one of those quiet moments where nothing is demanded of you.",
    ]
    closing_variants = [
        "Now let the breaths become smaller, quieter, almost private.",
        "If you notice my voice fading from your attention, that is a good thing. You can keep drifting.",
        "Stay with the softness. Stay with the support beneath you. Let the rest of the night do the rest.",
    ]

    def choose(options: list[str], label: str) -> str:
        return choose_spoken_variant(options, f"{seed}::{label}")

    def choose_many(options: list[str], count: int, label: str) -> list[str]:
        count = max(1, min(count, len(options)))
        picks = pick_deterministic_items(
            [{"name": f"{label}-{index}", "line": option} for index, option in enumerate(options)],
            count,
            f"{seed}::{label}",
        )
        return [item["line"] for item in picks]

    selected_openings = choose_many(opening_variants, 3, "openings")
    selected_settling = choose_many(settling_lines, 4, "settling")
    selected_imagery = choose_many(imagery_lines, 4, "imagery")
    selected_companion = choose_many(companion_lines, 4, "companion")
    rotating_breaths = choose_many(breath_lines, len(breath_lines), "breath")
    rotating_reassurance = choose_many(reassurance_lines, len(reassurance_lines), "reassurance")
    practice_preferences = {str(item).strip().lower() for item in theme.get("practice_preferences", [])}
    is_zen_theme = bool(
        {"禅宗观照", "zen", "zen sitting", "shikantaza"} & practice_preferences
    )
    zen_lines = [
        "For now, nothing needs to be changed. Let this moment be exactly as it is, and let that be enough.",
        "You do not have to chase away thought. Simply notice it, and let it pass without following it anywhere.",
        "Sit inwardly with the night the way you might sit beside a quiet window, not asking for anything, only keeping company.",
        "Awake or half asleep, you can remain simple here, breathing, resting, letting the mind widen instead of tighten.",
    ]

    lines_with_pause: list[tuple[str, int]] = [
        (theme["opening"], 7200),
        (selected_openings[0], 8600),
        (selected_openings[1], 9200),
    ]

    for line in selected_settling[:2]:
        lines_with_pause.append((line, 9000))
    lines_with_pause.append((theme["body_focus"], 9800))
    for line in selected_settling[2:]:
        lines_with_pause.append((line, 9600))
    lines_with_pause.append((selected_openings[2], 10200))

    lines_with_pause.append((rotating_breaths[0], 11200))
    lines_with_pause.append((rotating_reassurance[0], 9600))
    lines_with_pause.append((selected_imagery[0], 12200))
    if is_zen_theme:
        lines_with_pause.append((zen_lines[0], 11400))

    for index in range(drift_cycles):
        lines_with_pause.append((rotating_breaths[(index + 1) % len(rotating_breaths)], 10800))
        lines_with_pause.append((rotating_reassurance[(index + 1) % len(rotating_reassurance)], 9800))
        if index in {1, 3, 5, 7}:
            imagery_index = min(index // 2 + 1, len(selected_imagery) - 1)
            lines_with_pause.append((selected_imagery[imagery_index], 12600))
        if index in {2, 6}:
            companion_index = min(index // 2 - 1, len(selected_companion) - 1)
            lines_with_pause.append((selected_companion[companion_index], 11000))
        if is_zen_theme and index in {1, 4, 7}:
            zen_index = min(index // 3 + 1, len(zen_lines) - 1)
            lines_with_pause.append((zen_lines[zen_index], 11600))
        if index == max(2, drift_cycles // 2):
            lines_with_pause.append(("Notice how the body may already be a little farther away from the day than when we began.", 10400))
            lines_with_pause.append(("You do not need to check whether it is working. Checking wakes the mind back up. Let not knowing be part of the rest.", 11800))

    lines_with_pause.extend(
        [
            (selected_companion[-2], 11200),
            (selected_companion[-1], 11800),
            (closing_variants[0], 12400),
            (closing_variants[1], 13200),
            (theme["closing"], 13800),
            (closing_variants[2], 15000),
        ]
    )

    spoken_blocks = build_spoken_blocks(lines_with_pause)
    guidance = compact_blank_lines([block["text"] for block in spoken_blocks])
    return {
        "title": theme["name"],
        "subtitle": theme["subtitle"],
        "duration_minutes": duration_minutes,
        "script_style": script_style,
        "traditions": [],
        "full_text": guidance,
        "spoken_blocks": spoken_blocks,
    }


def build_image_prompt(theme: dict, video_title: str) -> str:
    keywords = ", ".join(theme["image_keywords"])
    return (
        f"Create a calming static meditation background for the title '{video_title}', "
        f"cinematic, minimal, serene, centered composition, {keywords}, no people, no text, 16:9."
    )


def build_music_prompt(theme: dict, config: dict, duration_minutes: int) -> str:
    music_tags = normalize_tags(config.get("music", {}).get("default_tags", [])) + normalize_tags(theme.get("music_tags", []))
    descriptive_tags = ", ".join(dict.fromkeys(music_tags)) or "meditation, ambient, slow, instrumental"
    return (
        f"Generate an original meditation background track for the theme '{theme['name']}'. "
        f"Mood: {theme['subtitle']}. Style: {descriptive_tags}. "
        f"Instrumental only, no vocals, no percussion spikes, soft texture, seamless loop, "
        f"{duration_minutes} minutes, suitable for guided meditation voiceover."
    )


def build_music_request(theme: dict, config: dict, duration_minutes: int, bundle_name: str) -> dict:
    prompt = build_music_prompt(theme, config, duration_minutes)
    generation = config.get("music_generation", {})
    return {
        "provider": generation.get("provider", "manual"),
        "theme": theme["name"],
        "subtitle": theme["subtitle"],
        "duration_minutes": duration_minutes,
        "prompt": prompt,
        "tags": normalize_tags(config.get("music", {}).get("default_tags", [])) + normalize_tags(theme.get("music_tags", [])),
        "expected_output_file": f"{slugify(bundle_name)}-music.mp3",
        "extra_payload": generation.get("extra_payload", {}),
    }


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=True)


def find_ffmpeg_binary() -> Path | None:
    candidates = [
        Path("/Applications/net.downloadhelper.coapp.app/Contents/MacOS/ffmpeg"),
        Path("/Applications/CapCut.app/Contents/Resources/ffmpeg"),
        Path("/Applications/VideoFusion-macOS.app/Contents/Resources/ffmpeg"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    discovered = shutil.which("ffmpeg")
    return Path(discovered) if discovered else None


def convert_audio_with_ffmpeg(
    input_path: Path,
    output_path: Path,
    codec: str = "libmp3lame",
    bitrate: str = "128k",
    sample_rate: int = 44100,
) -> None:
    ffmpeg_bin = find_ffmpeg_binary()
    if not ffmpeg_bin:
        raise FileNotFoundError("ffmpeg binary not found.")
    run_command(
        [
            str(ffmpeg_bin),
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            codec,
            "-b:a",
            bitrate,
            "-ar",
            str(sample_rate),
            str(output_path),
        ]
    )


def pad_audio_to_duration_with_ffmpeg(
    input_path: Path,
    output_path: Path,
    target_duration_seconds: float,
    sample_rate: int | None = None,
) -> None:
    ffmpeg_bin = find_ffmpeg_binary()
    if not ffmpeg_bin:
        raise FileNotFoundError("ffmpeg binary not found.")
    command = [
        str(ffmpeg_bin),
        "-y",
        "-i",
        str(input_path),
        "-af",
        "apad",
        "-t",
        f"{max(0.0, target_duration_seconds):.3f}",
    ]
    suffix = output_path.suffix.lower()
    if suffix == ".mp3":
        command.extend(["-acodec", "libmp3lame", "-b:a", "128k", "-ar", str(sample_rate or 44100)])
    elif suffix == ".wav":
        command.extend(["-acodec", "pcm_s16le"])
        if sample_rate:
            command.extend(["-ar", str(sample_rate)])
    command.append(str(output_path))
    run_command(command)


def convert_audio_with_afconvert(
    input_path: Path,
    output_path: Path,
    file_format: str,
    data_format: str,
    sample_rate: int | None = None,
    channels: int | None = None,
) -> None:
    resolved_data_format = f"{data_format}@{sample_rate}" if sample_rate else data_format
    command = ["afconvert", str(input_path), "-o", str(output_path), "-f", file_format, "-d", resolved_data_format]
    if channels:
        command.extend(["-c", str(channels)])
    run_command(command)


def create_final_audio_mix(bundle_dir: Path, voice_path: Path, music_path: Path) -> Path | None:
    if not voice_path.exists() or not music_path.exists():
        return None

    temp_music_wav = bundle_dir / "_music_temp.wav"
    mixed_wav = bundle_dir / "final_audio_mix.wav"
    mixed_mp3 = bundle_dir / "final_audio_mix.mp3"

    try:
        with wave.open(str(voice_path), "rb") as voice_file:
            channels = voice_file.getnchannels()
            sample_width = voice_file.getsampwidth()
            sample_rate = voice_file.getframerate()
            voice_frames = voice_file.readframes(voice_file.getnframes())

        if sample_width != 2:
            return None

        convert_audio_with_afconvert(
            music_path,
            temp_music_wav,
            file_format="WAVE",
            data_format="LEI16",
            sample_rate=sample_rate,
            channels=channels,
        )

        with wave.open(str(temp_music_wav), "rb") as music_file:
            music_frames = music_file.readframes(music_file.getnframes())
            music_channels = music_file.getnchannels()
            music_width = music_file.getsampwidth()
            music_rate = music_file.getframerate()

        if music_channels != channels or music_width != sample_width or music_rate != sample_rate:
            return None

        if len(music_frames) < len(voice_frames):
            repeats = (len(voice_frames) // len(music_frames)) + 1
            music_frames = (music_frames * repeats)[: len(voice_frames)]
        else:
            music_frames = music_frames[: len(voice_frames)]

        voice_samples = array("h")
        voice_samples.frombytes(voice_frames)
        music_samples = array("h")
        music_samples.frombytes(music_frames)

        mixed_samples = array("h")
        for voice_sample, music_sample in zip(voice_samples, music_samples):
            mixed_value = int(voice_sample * 0.92 + music_sample * 0.16)
            if mixed_value > 32767:
                mixed_value = 32767
            elif mixed_value < -32768:
                mixed_value = -32768
            mixed_samples.append(mixed_value)

        with wave.open(str(mixed_wav), "wb") as output_file:
            output_file.setnchannels(channels)
            output_file.setsampwidth(sample_width)
            output_file.setframerate(sample_rate)
            output_file.writeframes(mixed_samples.tobytes())

        try:
            convert_audio_with_ffmpeg(mixed_wav, mixed_mp3)
        except (FileNotFoundError, subprocess.CalledProcessError):
            convert_audio_with_afconvert(
                mixed_wav,
                mixed_mp3,
                file_format="MPG3",
                data_format=".mp3",
            )
        return mixed_mp3
    except (subprocess.CalledProcessError, wave.Error, OSError):
        return None
    finally:
        for temp_path in [temp_music_wav]:
            if temp_path.exists():
                temp_path.unlink()


def convert_voice_wav_to_mp3(bundle_dir: Path, voice_path: Path) -> Path | None:
    if not voice_path.exists() or voice_path.suffix.lower() != ".wav":
        return None
    output_path = bundle_dir / "voiceover.mp3"
    try:
        try:
            convert_audio_with_ffmpeg(voice_path, output_path)
        except (FileNotFoundError, subprocess.CalledProcessError):
            convert_audio_with_afconvert(
                voice_path,
                output_path,
                file_format="MPG3",
                data_format=".mp3",
            )
        return output_path
    except subprocess.CalledProcessError:
        return None


def ensure_voice_duration(bundle_dir: Path, voice_path: Path, target_duration_seconds: float) -> Path:
    current_duration = safe_get_audio_duration(voice_path) or 0.0
    if current_duration + 1.0 >= target_duration_seconds:
        return voice_path
    padded_path = bundle_dir / f"{voice_path.stem}_padded{voice_path.suffix}"
    sample_rate = None
    if voice_path.suffix.lower() == ".wav":
        with wave.open(str(voice_path), "rb") as voice_file:
            sample_rate = voice_file.getframerate()
    pad_audio_to_duration_with_ffmpeg(
        voice_path,
        padded_path,
        target_duration_seconds=target_duration_seconds,
        sample_rate=sample_rate,
    )
    shutil.move(str(padded_path), str(voice_path))
    return voice_path


def write_binary_file(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def build_http_headers(config: dict) -> dict[str, str]:
    generation = config.get("music_generation", {})
    headers = {"Content-Type": "application/json"}
    auth_header = str(generation.get("auth_header", "")).strip()
    if auth_header:
        if ":" in auth_header:
            key, value = auth_header.split(":", 1)
            headers[key.strip()] = value.strip()
        else:
            headers["Authorization"] = auth_header
    return headers


def resolve_output_filename(response_payload: dict, request_payload: dict, config: dict) -> str:
    field = str(config.get("music_generation", {}).get("filename_field", "filename")).strip()
    filename = str(response_payload.get(field, "")).strip()
    return filename or request_payload["expected_output_file"]


def download_binary(url: str, timeout_seconds: int) -> bytes:
    with request.urlopen(url, timeout=timeout_seconds) as response:
        return response.read()


def generate_music_via_webhook(bundle_dir: Path, config: dict, music_request: dict) -> GeneratedMusicResult:
    generation = config.get("music_generation", {})
    endpoint = str(generation.get("endpoint", "")).strip()
    if not endpoint or endpoint == "https://example.com/generate-music":
        return GeneratedMusicResult(
            provider="webhook",
            status="skipped",
            prompt=music_request["prompt"],
            request_payload=music_request,
            output_file=None,
            source_url=None,
            message="Webhook endpoint 未配置，已只生成 music_request.json。",
        )

    payload = {
        "prompt": music_request["prompt"],
        "duration_minutes": music_request["duration_minutes"],
        "theme": music_request["theme"],
        "tags": music_request["tags"],
        **music_request.get("extra_payload", {}),
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers=build_http_headers(config),
        method=str(generation.get("method", "POST")).upper(),
    )
    timeout_seconds = int(generation.get("timeout_seconds", 120))
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        response_payload = json.loads(raw)
        download_field = str(generation.get("download_field", "audio_url")).strip()
        base64_field = str(generation.get("base64_field", "audio_base64")).strip()
        filename = resolve_output_filename(response_payload, music_request, config)
        output_path = bundle_dir / filename
        source_url = str(response_payload.get(download_field, "")).strip() or None
        if source_url:
            write_binary_file(output_path, download_binary(source_url, timeout_seconds))
        elif response_payload.get(base64_field):
            write_binary_file(output_path, base64.b64decode(response_payload[base64_field]))
        else:
            return GeneratedMusicResult(
                provider="webhook",
                status="failed",
                prompt=music_request["prompt"],
                request_payload=payload,
                output_file=None,
                source_url=None,
                message=f"接口返回中没有 `{download_field}` 或 `{base64_field}`。",
            )
        return GeneratedMusicResult(
            provider="webhook",
            status="generated",
            prompt=music_request["prompt"],
            request_payload=payload,
            output_file=filename,
            source_url=source_url,
            message="已通过 webhook 生成音乐。",
        )
    except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return GeneratedMusicResult(
            provider="webhook",
            status="failed",
            prompt=music_request["prompt"],
            request_payload=payload,
            output_file=None,
            source_url=None,
            message=f"自动生成音乐失败：{exc}",
        )


def maybe_generate_music(bundle_dir: Path, config: dict, music_request: dict) -> GeneratedMusicResult:
    provider = str(config.get("music_generation", {}).get("provider", "manual")).strip().lower()
    if provider == "webhook":
        return generate_music_via_webhook(bundle_dir, config, music_request)
    return GeneratedMusicResult(
        provider=provider or "manual",
        status="manual",
        prompt=music_request["prompt"],
        request_payload=music_request,
        output_file=None,
        source_url=None,
        message="当前为手动模式，已生成 music_request.json。",
    )


def post_json(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def post_binary(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int) -> bytes:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        return response.read()


def get_json(url: str, headers: dict[str, str], timeout_seconds: int) -> dict:
    req = request.Request(url, headers=headers, method="GET")
    with request.urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def build_image_request(theme: dict, config: dict, title: str, bundle_name: str) -> dict:
    prompt = build_image_prompt(theme, title)
    image_config = config.get("image_generation", {})
    output_format = str(image_config.get("output_format", "png")).lower()
    return {
        "provider": image_config.get("provider", "manual"),
        "prompt": prompt,
        "model": image_config.get("model", "gpt-image-1"),
        "size": image_config.get("size", "1536x1024"),
        "quality": image_config.get("quality", "high"),
        "background": image_config.get("background", "opaque"),
        "output_format": output_format,
        "expected_output_file": f"{slugify(bundle_name)}-image.{output_format}",
    }


def generate_image_via_openai(bundle_dir: Path, config: dict, image_request: dict) -> GeneratedAssetResult:
    image_config = config.get("image_generation", {})
    api_key = str(image_config.get("api_key", "")).strip()
    if not api_key:
        return GeneratedAssetResult(
            provider="openai",
            status="skipped",
            request_payload=image_request,
            output_file=None,
            source_url=None,
            message="OpenAI API key 未配置，已只生成 image_request.json。",
        )

    payload = {
        "model": image_request["model"],
        "prompt": image_request["prompt"],
        "size": image_request["size"],
        "quality": image_request["quality"],
        "background": image_request["background"],
    }
    timeout_seconds = 120
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    try:
        response_payload = post_json(
            "https://api.openai.com/v1/images/generations",
            payload,
            headers,
            timeout_seconds,
        )
        data_items = response_payload.get("data", [])
        if not data_items:
            return GeneratedAssetResult(
                provider="openai",
                status="failed",
                request_payload=payload,
                output_file=None,
                source_url=None,
                message="OpenAI 图片接口没有返回 data。",
            )
        image_item = data_items[0]
        output_path = bundle_dir / image_request["expected_output_file"]
        if image_item.get("b64_json"):
            write_binary_file(output_path, base64.b64decode(image_item["b64_json"]))
            return GeneratedAssetResult(
                provider="openai",
                status="generated",
                request_payload=payload,
                output_file=output_path.name,
                source_url=None,
                message="已通过 OpenAI Images API 生成静态图片。",
            )
        image_url = str(image_item.get("url", "")).strip()
        if image_url:
            write_binary_file(output_path, download_binary(image_url, timeout_seconds))
            return GeneratedAssetResult(
                provider="openai",
                status="generated",
                request_payload=payload,
                output_file=output_path.name,
                source_url=image_url,
                message="已通过 OpenAI Images API 生成静态图片。",
            )
        return GeneratedAssetResult(
            provider="openai",
            status="failed",
            request_payload=payload,
            output_file=None,
            source_url=None,
            message="OpenAI 图片接口没有返回 b64_json 或 url。",
        )
    except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return GeneratedAssetResult(
            provider="openai",
            status="failed",
            request_payload=payload,
            output_file=None,
            source_url=None,
            message=f"OpenAI 图片生成失败：{exc}",
        )


def maybe_generate_image(bundle_dir: Path, config: dict, image_request: dict) -> GeneratedAssetResult:
    provider = str(config.get("image_generation", {}).get("provider", "manual")).strip().lower()
    if provider == "openai":
        return generate_image_via_openai(bundle_dir, config, image_request)
    return GeneratedAssetResult(
        provider=provider or "manual",
        status="manual",
        request_payload=image_request,
        output_file=None,
        source_url=None,
        message="当前为手动模式，已生成 image_request.json。",
    )


def generate_voice_via_elevenlabs(bundle_dir: Path, config: dict, voice_request: dict) -> GeneratedAssetResult:
    voice = config.get("voice_clone", {})
    api_key = str(voice.get("api_key", "")).strip()
    voice_id = str(voice.get("voice_id", "")).strip()
    if not api_key or not voice_id or voice_id == "replace-with-your-cloned-voice-id":
        return GeneratedAssetResult(
            provider="elevenlabs",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message="ElevenLabs api_key 或 voice_id 未配置，已只生成 voiceover_request.json。",
        )

    payload = {
        "text": voice_request["text"],
        "model_id": voice.get("model_id", "eleven_multilingual_v2"),
    }
    instructions = str(voice_request.get("style_instructions", "")).strip()
    if instructions:
        payload["voice_settings"] = {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.3,
            "use_speaker_boost": True,
        }
    output_format = str(voice.get("output_format", "mp3_44100_128")).strip()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{parse.quote(voice_id)}?output_format={parse.quote(output_format)}"
    headers = {
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    try:
        audio_bytes = post_binary(url, payload, headers, 180)
        suffix = ".mp3" if output_format.startswith("mp3") else ".wav"
        output_name = Path(voice_request["expected_output_file"]).with_suffix(suffix).name
        output_path = bundle_dir / output_name
        write_binary_file(output_path, audio_bytes)
        return GeneratedAssetResult(
            provider="elevenlabs",
            status="generated",
            request_payload=payload,
            output_file=output_path.name,
            source_url=None,
            message="已通过 ElevenLabs 生成克隆音色旁白。",
        )
    except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return GeneratedAssetResult(
            provider="elevenlabs",
            status="failed",
            request_payload=payload,
            output_file=None,
            source_url=None,
            message=f"ElevenLabs 旁白生成失败：{exc}",
        )


def generate_voice_via_volcengine(bundle_dir: Path, config: dict, voice_request: dict) -> GeneratedAssetResult:
    voice = config.get("voice_clone", {})
    volcengine = voice.get("volcengine", {})
    speaker = str(volcengine.get("speaker", "")).strip()
    api_key = str(volcengine.get("api_key", "")).strip() or str(volcengine.get("access_key", "")).strip()
    cluster = str(volcengine.get("cluster", "volcano_icl")).strip() or "volcano_icl"
    synth_url = str(volcengine.get("synth_url", "")).strip()
    timeout_seconds = max(60, int(volcengine.get("request_timeout_seconds", 1800)))
    audio_format = str(volcengine.get("audio_format", "mp3")).strip().lower() or "mp3"
    speed_ratio = float(volcengine.get("speed_ratio", 0.92))
    max_chunk_chars = int(volcengine.get("max_chunk_chars", 170))

    if not api_key or not speaker:
        return GeneratedAssetResult(
            provider="volcengine_v1",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message="火山引擎 api_key 或 speaker 未配置，已只生成 voiceover_request.json。",
        )

    raw_blocks = voice_request.get("spoken_blocks") if isinstance(voice_request.get("spoken_blocks"), list) else []
    if raw_blocks:
        chunks = explode_spoken_blocks(raw_blocks, max_chunk_chars)
    else:
        chunks = [{"text": text, "pause_after_ms": 0} for text in split_voice_text(voice_request["text"], max_chunk_chars)]
    segment_dir = bundle_dir / "voice_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "chunk_count": len(chunks),
        "speaker": speaker,
        "cluster": cluster,
        "audio_format": audio_format,
    }

    try:
        output_path = bundle_dir / Path(voice_request["expected_output_file"]).with_suffix(f".{audio_format}").name
        segment_files: list[Path] = []
        response_meta: list[dict] = []
        params_signature: tuple[int, int, int, str] | None = None
        for index, chunk in enumerate(chunks, start=1):
            chunk_text = chunk["text"]
            pause_after_ms = max(0, int(chunk.get("pause_after_ms", 0)))
            req_id = hashlib.sha256(
                f"{bundle_dir.name}:{speaker}:{index}:{chunk_text[:64]}".encode("utf-8")
            ).hexdigest()[:32]
            payload = {
                "app": {
                    "cluster": cluster,
                },
                "user": {
                    "uid": slugify(bundle_dir.name) or "meditation-bot",
                },
                "audio": {
                    "voice_type": speaker,
                    "encoding": audio_format,
                    "speed_ratio": speed_ratio,
                },
                "request": {
                    "reqid": req_id,
                    "text": chunk_text,
                    "operation": "query",
                },
            }
            curl_command = [
                "curl",
                "-sS",
                "-L",
                "-X",
                "POST",
                synth_url,
                "-H",
                f"x-api-key: {api_key}",
                "-H",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
            ]
            response = subprocess.run(
                curl_command,
                input=json.dumps(payload).encode("utf-8"),
                capture_output=True,
                timeout=timeout_seconds,
                check=True,
            )
            response_payload = json.loads(response.stdout.decode("utf-8", errors="ignore"))
            if int(response_payload.get("code", -1)) != 3000:
                raise ValueError(
                    f"第{index}段失败: {response_payload.get('message', '火山引擎未成功返回音频数据')}"
                )
            audio_data = response_payload.get("data")
            if not isinstance(audio_data, str) or not audio_data:
                raise ValueError(f"第{index}段未返回音频数据: {response_payload}")

            segment_path = segment_dir / f"segment_{index:03d}.{audio_format}"
            write_binary_file(segment_path, base64.b64decode(audio_data))
            segment_files.append(segment_path)
            if audio_format == "wav":
                with wave.open(str(segment_path), "rb") as generated_wav:
                    params_signature = (
                        generated_wav.getnchannels(),
                        generated_wav.getsampwidth(),
                        generated_wav.getframerate(),
                        generated_wav.getcomptype(),
                    )
            if pause_after_ms > 0 and audio_format == "wav":
                pause_path = segment_dir / f"segment_{index:03d}_pause.wav"
                nchannels, sampwidth, framerate, _ = params_signature or (1, 2, 24000, "NONE")
                write_silence_wav(
                    pause_path,
                    pause_after_ms,
                    nchannels=nchannels,
                    sampwidth=sampwidth,
                    framerate=framerate,
                )
                segment_files.append(pause_path)
            response_meta.append(
                {
                    "index": index,
                    "reqid": response_payload.get("reqid"),
                    "code": response_payload.get("code"),
                    "message": response_payload.get("message"),
                    "addition": response_payload.get("addition"),
                    "text": chunk_text,
                    "output_file": segment_path.name,
                    "pause_after_ms": pause_after_ms,
                }
            )

        if audio_format == "wav":
            concatenate_wav_files(segment_files, output_path)
        elif len(segment_files) == 1:
            shutil.copy2(segment_files[0], output_path)
        else:
            raise ValueError("非 wav 格式下暂不支持多段自动拼接，请将 audio_format 改为 wav。")

        return GeneratedAssetResult(
            provider="volcengine_v1",
            status="generated",
            request_payload={
                "chunk_count": len(chunks),
                "chunks": response_meta,
            },
            output_file=output_path.name,
            source_url=None,
            message=f"已通过火山引擎 V1 克隆语音接口生成旁白，共 {len(chunks)} 段。",
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return GeneratedAssetResult(
            provider="volcengine_v1",
            status="failed",
            request_payload=payload,
            output_file=None,
            source_url=None,
            message=f"火山引擎旁白生成失败：{exc}",
        )


def generate_voice_via_cosyvoice(bundle_dir: Path, config: dict, voice_request: dict) -> GeneratedAssetResult:
    voice = config.get("voice_clone", {})
    cosyvoice = voice.get("cosyvoice", {})
    python_bin = Path(str(cosyvoice.get("python_bin", "/tmp/cosyvoice-conda/bin/python")))
    script_path = Path(str(cosyvoice.get("script_path", "tools/cosyvoice_runner.py")))
    reference_audio = Path(str(voice.get("reference_audio", "")).strip())
    prompt_text = str(voice.get("reference_transcript", "")).strip()
    model_dir = Path(str(cosyvoice.get("model_dir", "third_party/CosyVoice/pretrained_models/CosyVoice2-0.5B")))
    temp_dir = Path(str(cosyvoice.get("temp_dir", "tmp/cosyvoice")))
    repo_dir = Path(str(cosyvoice.get("repo_dir", "third_party/CosyVoice")))
    max_chunk_chars = int(cosyvoice.get("max_chunk_chars", 48))

    if not python_bin.exists():
        return GeneratedAssetResult(
            provider="cosyvoice_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message=f"找不到 CosyVoice Python 环境：{python_bin}",
        )
    if not script_path.exists():
        return GeneratedAssetResult(
            provider="cosyvoice_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message=f"找不到 CosyVoice runner 脚本：{script_path}",
        )
    if not model_dir.exists():
        return GeneratedAssetResult(
            provider="cosyvoice_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message=f"找不到 CosyVoice 模型目录：{model_dir}",
        )
    if not reference_audio.exists():
        return GeneratedAssetResult(
            provider="cosyvoice_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message="未配置 reference_audio 或文件不存在。",
        )

    output_path = bundle_dir / Path(voice_request["expected_output_file"]).with_suffix(".wav").name
    temp_dir.mkdir(parents=True, exist_ok=True)
    segment_dir = bundle_dir / "voice_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    segments = split_voice_text(str(voice_request["text"]), max_chunk_chars)
    temp_run_dir = temp_dir / f"bundle-{bundle_dir.name}"
    temp_run_dir.mkdir(parents=True, exist_ok=True)
    segments_path = temp_run_dir / "segments.json"
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = [
        str(python_bin),
        str(script_path),
        "--texts-file",
        str(segments_path),
        "--reference-audio",
        str(reference_audio),
        "--output",
        str(output_path),
        "--model-dir",
        str(model_dir),
        "--temp-dir",
        str(temp_run_dir),
        "--repo-dir",
        str(repo_dir),
    ]
    if prompt_text:
        command.extend(["--prompt-text", prompt_text])
    try:
        env = dict(os.environ)
        env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        result = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
        output_segments = copy_generated_segments(temp_run_dir / "segments", segment_dir)
        return GeneratedAssetResult(
            provider="cosyvoice_local",
            status="generated",
            request_payload={
                "command": command,
                "segments": segments,
                "segment_files": [path.name for path in output_segments],
            },
            output_file=output_path.name,
            source_url=None,
            message=result.stdout.strip() or "已通过 CosyVoice 本地分段生成克隆音色旁白。",
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return GeneratedAssetResult(
            provider="cosyvoice_local",
            status="failed",
            request_payload={
                "command": command,
                "segments": segments,
            },
            output_file=None,
            source_url=None,
            message=f"CosyVoice 本地生成失败：{stderr or exc}",
        )


def generate_voice_via_indextts(bundle_dir: Path, config: dict, voice_request: dict) -> GeneratedAssetResult:
    voice = config.get("voice_clone", {})
    indextts = voice.get("indextts", {})
    python_bin = Path(str(indextts.get("python_bin", "third_party/index-tts/.venv/bin/python")))
    script_path = Path(str(indextts.get("script_path", "tools/indextts_runner.py")))
    reference_audio = Path(str(voice.get("reference_audio", "")).strip())
    model_dir = Path(str(indextts.get("model_dir", "third_party/index-tts/checkpoints")))
    config_path = Path(str(indextts.get("config_path", "third_party/index-tts/checkpoints/config.yaml")))
    temp_dir = Path(str(indextts.get("temp_dir", "tmp/indextts")))
    repo_dir = Path(str(indextts.get("repo_dir", "third_party/index-tts")))
    max_chunk_chars = int(indextts.get("max_chunk_chars", 56))
    device = str(indextts.get("device", "cpu")).strip() or "cpu"

    if not python_bin.exists():
        return GeneratedAssetResult(
            provider="indextts_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message=f"找不到 IndexTTS Python 环境：{python_bin}",
        )
    if not script_path.exists():
        return GeneratedAssetResult(
            provider="indextts_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message=f"找不到 IndexTTS runner 脚本：{script_path}",
        )
    if not model_dir.exists():
        return GeneratedAssetResult(
            provider="indextts_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message=f"找不到 IndexTTS 模型目录：{model_dir}",
        )
    if not config_path.exists():
        return GeneratedAssetResult(
            provider="indextts_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message=f"找不到 IndexTTS 配置文件：{config_path}",
        )
    if not reference_audio.exists():
        return GeneratedAssetResult(
            provider="indextts_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message="未配置 reference_audio 或文件不存在。",
        )

    output_path = bundle_dir / Path(voice_request["expected_output_file"]).with_suffix(".wav").name
    temp_dir.mkdir(parents=True, exist_ok=True)
    segment_dir = bundle_dir / "voice_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    segments = split_voice_text(str(voice_request["text"]), max_chunk_chars)
    temp_run_dir = temp_dir / f"bundle-{bundle_dir.name}"
    temp_run_dir.mkdir(parents=True, exist_ok=True)
    segments_path = temp_run_dir / "segments.json"
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = [
        str(python_bin),
        str(script_path),
        "--texts-file",
        str(segments_path),
        "--reference-audio",
        str(reference_audio),
        "--output",
        str(output_path),
        "--model-dir",
        str(model_dir),
        "--config-path",
        str(config_path),
        "--temp-dir",
        str(temp_run_dir),
        "--repo-dir",
        str(repo_dir),
        "--device",
        device,
    ]
    try:
        env = dict(os.environ)
        env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        env.setdefault("MPLCONFIGDIR", str(temp_run_dir / "mplconfig"))
        result = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
        output_segments = copy_generated_segments(temp_run_dir / "segments", segment_dir)
        return GeneratedAssetResult(
            provider="indextts_local",
            status="generated",
            request_payload={
                "command": command,
                "segments": segments,
                "segment_files": [path.name for path in output_segments],
            },
            output_file=output_path.name,
            source_url=None,
            message=result.stdout.strip() or "已通过 IndexTTS 本地分段生成克隆音色旁白。",
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        return GeneratedAssetResult(
            provider="indextts_local",
            status="failed",
            request_payload={
                "command": command,
                "segments": segments,
            },
            output_file=None,
            source_url=None,
            message=f"IndexTTS 本地生成失败：{detail}",
        )


def generate_voice_via_say(bundle_dir: Path, config: dict, voice_request: dict) -> GeneratedAssetResult:
    voice = config.get("voice_clone", {})
    say_config = voice.get("say", {})
    say_bin = shutil.which("say")
    if not say_bin:
        return GeneratedAssetResult(
            provider="say_local",
            status="skipped",
            request_payload=voice_request,
            output_file=None,
            source_url=None,
            message="找不到 macOS say 命令。",
        )

    voice_name = str(say_config.get("voice", "Samantha")).strip() or "Samantha"
    rate = max(80, int(say_config.get("rate", 115)))
    sample_rate = max(8000, int(say_config.get("sample_rate", 24000)))
    channels = max(1, int(say_config.get("channels", 1)))
    max_chunk_chars = max(40, int(say_config.get("max_chunk_chars", 220)))

    raw_blocks = voice_request.get("spoken_blocks") if isinstance(voice_request.get("spoken_blocks"), list) else []
    blocks = explode_spoken_blocks(raw_blocks, max_chunk_chars) if raw_blocks else [
        {"text": text, "pause_after_ms": 0} for text in split_voice_text(str(voice_request["text"]), max_chunk_chars)
    ]
    if not blocks:
        return GeneratedAssetResult(
            provider="say_local",
            status="failed",
            request_payload={"voice": voice_name, "rate": rate},
            output_file=None,
            source_url=None,
            message="没有可用于本地 say 生成的文本片段。",
        )

    output_path = bundle_dir / Path(voice_request["expected_output_file"]).with_suffix(".wav").name
    segment_dir = bundle_dir / "voice_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    segment_files: list[Path] = []
    response_meta: list[dict] = []
    params_signature: tuple[int, int, int, str] | None = None

    try:
        for index, block in enumerate(blocks, start=1):
            text = str(block.get("text", "")).strip()
            pause_after_ms = max(0, int(block.get("pause_after_ms", 0)))
            if not text:
                continue

            aiff_path = segment_dir / f"segment_{index:03d}.aiff"
            wav_path = segment_dir / f"segment_{index:03d}.wav"
            subprocess.run(
                [say_bin, "-v", voice_name, "-r", str(rate), "-o", str(aiff_path), text],
                check=True,
                capture_output=True,
                text=True,
            )
            convert_audio_with_afconvert(
                aiff_path,
                wav_path,
                file_format="WAVE",
                data_format="LEI16",
                sample_rate=sample_rate,
                channels=channels,
            )
            segment_duration = safe_get_audio_duration(wav_path)
            if segment_duration is None or segment_duration <= 0.05:
                raise ValueError(
                    f"macOS say generated an empty audio segment for chunk {index}: {text[:80]}"
                )
            segment_files.append(wav_path)
            with wave.open(str(wav_path), "rb") as generated_wav:
                params_signature = (
                    generated_wav.getnchannels(),
                    generated_wav.getsampwidth(),
                    generated_wav.getframerate(),
                    generated_wav.getcomptype(),
                )
            if pause_after_ms > 0:
                pause_path = segment_dir / f"segment_{index:03d}_pause.wav"
                nchannels, sampwidth, framerate, _ = params_signature or (channels, 2, sample_rate, "NONE")
                write_silence_wav(
                    pause_path,
                    pause_after_ms,
                    nchannels=nchannels,
                    sampwidth=sampwidth,
                    framerate=framerate,
                )
                segment_files.append(pause_path)
            response_meta.append(
                {
                    "index": index,
                    "text": text,
                    "output_file": wav_path.name,
                    "pause_after_ms": pause_after_ms,
                }
            )

        concatenate_wav_files(segment_files, output_path)
        return GeneratedAssetResult(
            provider="say_local",
            status="generated",
            request_payload={
                "voice": voice_name,
                "rate": rate,
                "chunk_count": len(response_meta),
                "chunks": response_meta,
            },
            output_file=output_path.name,
            source_url=None,
            message=f"已通过 macOS say 本地生成旁白，共 {len(response_meta)} 段。",
        )
    except (subprocess.CalledProcessError, ValueError, wave.Error, OSError) as exc:
        return GeneratedAssetResult(
            provider="say_local",
            status="failed",
            request_payload={
                "voice": voice_name,
                "rate": rate,
                "chunk_count": len(blocks),
            },
            output_file=None,
            source_url=None,
            message=f"macOS say 本地生成失败：{exc}",
        )


def maybe_generate_voice(bundle_dir: Path, config: dict, voice_request: dict) -> GeneratedAssetResult:
    provider = str(config.get("voice_clone", {}).get("provider", "manual")).strip().lower()
    if provider == "elevenlabs":
        return generate_voice_via_elevenlabs(bundle_dir, config, voice_request)
    if provider in {"volcengine_async", "volcengine_v1"}:
        return generate_voice_via_volcengine(bundle_dir, config, voice_request)
    if provider == "cosyvoice_local":
        return generate_voice_via_cosyvoice(bundle_dir, config, voice_request)
    if provider == "indextts_local":
        return generate_voice_via_indextts(bundle_dir, config, voice_request)
    if provider == "say_local":
        return generate_voice_via_say(bundle_dir, config, voice_request)
    return GeneratedAssetResult(
        provider=provider or "manual",
        status="manual",
        request_payload=voice_request,
        output_file=None,
        source_url=None,
        message="当前为手动模式，已生成 voiceover_request.json。",
    )


def build_svg(title: str, subtitle: str, theme: dict) -> str:
    accent = {
        "清晨安定": ("#214765", "#cc9b52"),
        "深度放松": ("#10263f", "#8bb0d1"),
        "睡前释放": ("#111827", "#9e86ff"),
        "情绪舒缓": ("#1a4338", "#d8c27a"),
        "专注回归": ("#604c2a", "#f2dfb0"),
    }.get(theme["name"], ("#1c3c52", "#d0ad6f"))
    return dedent(
        f"""\
        <svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
          <defs>
            <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="{accent[0]}"/>
              <stop offset="100%" stop-color="{accent[1]}"/>
            </linearGradient>
            <radialGradient id="light" cx="50%" cy="40%" r="55%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.24"/>
              <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
            </radialGradient>
          </defs>
          <rect width="1920" height="1080" fill="url(#bg)"/>
          <rect width="1920" height="1080" fill="url(#light)"/>
          <circle cx="960" cy="420" r="170" fill="none" stroke="#f7f1df" stroke-width="8" opacity="0.5"/>
          <circle cx="960" cy="420" r="230" fill="none" stroke="#f7f1df" stroke-width="3" opacity="0.35"/>
          <text x="960" y="740" text-anchor="middle" fill="#fffaf0" font-size="88" font-family="PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif">
            {escape_xml(title)}
          </text>
          <text x="960" y="820" text-anchor="middle" fill="#fff7e7" font-size="40" font-family="PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif" opacity="0.95">
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


def build_srt(script_text: str, segment_seconds: int) -> str:
    lines = [line.strip() for line in script_text.splitlines() if line.strip()]
    segments = []
    for index, line in enumerate(lines, start=1):
        start = (index - 1) * segment_seconds
        end = start + max(4, segment_seconds - 1)
        segments.extend(
            [
                str(index),
                f"{format_hms(start)},000 --> {format_hms(end)},000",
                line,
                "",
            ]
        )
    return "\n".join(segments).strip() + "\n"


def build_voice_request(config: dict, script: dict, output_name: str) -> dict:
    voice = config.get("voice_clone", {})
    return {
        "provider": voice.get("provider", "manual"),
        "voice_id": voice.get("voice_id", ""),
        "speaker_name": voice.get("speaker_name", ""),
        "style_instructions": voice.get("instructions", ""),
        "text": script["full_text"],
        "spoken_blocks": script.get("spoken_blocks", []),
        "expected_output_file": output_name,
        "notes": "把这个 JSON 发送给你的克隆音色服务，生成旁白后放回当前目录。",
    }


def build_jianying_notes(bundle_name: str, visual_filename: str, music_filename: str | None, voice_filename: str) -> str:
    lines = [
        f"剪映专业版每日冥想视频导入说明：{bundle_name}",
        "",
        "1. 新建 16:9 横版项目。",
        f"2. 导入 `{visual_filename}` 作为静态主视觉，拉满全片长度。",
    ]
    if music_filename:
        lines.append(f"3. 导入背景音乐 `{music_filename}`，并把长度对齐到整条时间线。")
        lines.append(f"4. 导入克隆音色生成后的旁白文件 `{voice_filename}`，放在主音轨。")
        lines.append("5. 导入 `captions.srt` 作为字幕。")
        lines.append("6. 如有真实生成图片，请替换 `cover.svg` 或放在其上方。")
        lines.append("7. 导出 1080p H.264。")
    else:
        lines.append(f"3. 导入克隆音色生成后的旁白文件 `{voice_filename}`，放在主音轨。")
        lines.append("4. 导入 `captions.srt` 作为字幕。")
        lines.append("5. 如有真实生成图片，请替换 `cover.svg` 或放在其上方。")
        lines.append("6. 导出 1080p H.264。")
    lines.extend(
        [
            "",
            "如果你暂时还没接通克隆音色接口，可以先用 `voiceover_request.json` 里的文字去手动生成配音。",
        ]
    )
    return "\n".join(lines) + "\n"


def next_output_dir(root: Path, target_date: date, title: str) -> Path:
    base = root / "output" / f"{target_date.isoformat()}-{slugify(title)}"
    if not base.exists():
        return base
    suffix = 2
    while True:
        candidate = root / "output" / f"{target_date.isoformat()}-{slugify(title)}-{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1


def write_bundle(
    root: Path,
    target_date: date,
    config: dict,
    theme: dict,
    music: AudioTrack | None,
    forced_duration_minutes: int | None = None,
) -> Path:
    duration_minutes = forced_duration_minutes or choose_duration_minutes(config, target_date, theme)
    segment_seconds = int(config.get("caption_segment_seconds", 12))
    script_style = str(config.get("script_style", "human_spoken")).strip().lower()
    script = build_meditation_script(theme, duration_minutes, target_date, script_style)
    bundle_dir = next_output_dir(root, target_date, script["title"])
    bundle_dir.mkdir(parents=True, exist_ok=False)

    voice_filename = "voiceover.wav"
    image_prompt = build_image_prompt(theme, script["title"])
    image_request = build_image_request(theme, config, script["title"], bundle_dir.name)
    music_prompt = build_music_prompt(theme, config, duration_minutes)
    music_request = build_music_request(theme, config, duration_minutes, bundle_dir.name)
    captions = build_srt(script["full_text"], segment_seconds)
    cover_svg = build_svg(script["title"], script["subtitle"], theme)
    voice_request = build_voice_request(config, script, voice_filename)

    (bundle_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (bundle_dir / "voiceover_script.txt").write_text(script["full_text"] + "\n", encoding="utf-8")
    (bundle_dir / "captions.srt").write_text(captions, encoding="utf-8")
    (bundle_dir / "image_prompt.txt").write_text(image_prompt + "\n", encoding="utf-8")
    (bundle_dir / "image_request.json").write_text(json.dumps(image_request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (bundle_dir / "music_prompt.txt").write_text(music_prompt + "\n", encoding="utf-8")
    (bundle_dir / "music_request.json").write_text(json.dumps(music_request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (bundle_dir / "voiceover_request.json").write_text(json.dumps(voice_request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (bundle_dir / "cover.svg").write_text(cover_svg, encoding="utf-8")
    generated_image = maybe_generate_image(bundle_dir, config, image_request)
    (bundle_dir / "image_generation_result.json").write_text(
        json.dumps(
            {
                "provider": generated_image.provider,
                "status": generated_image.status,
                "request_payload": generated_image.request_payload,
                "output_file": generated_image.output_file,
                "source_url": generated_image.source_url,
                "message": generated_image.message,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    generated_music = maybe_generate_music(bundle_dir, config, music_request)
    (bundle_dir / "music_generation_result.json").write_text(
        json.dumps(
            {
                "provider": generated_music.provider,
                "status": generated_music.status,
                "prompt": generated_music.prompt,
                "request_payload": generated_music.request_payload,
                "output_file": generated_music.output_file,
                "source_url": generated_music.source_url,
                "message": generated_music.message,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    generated_voice = maybe_generate_voice(bundle_dir, config, voice_request)
    (bundle_dir / "voice_generation_result.json").write_text(
        json.dumps(
            {
                "provider": generated_voice.provider,
                "status": generated_voice.status,
                "request_payload": generated_voice.request_payload,
                "output_file": generated_voice.output_file,
                "source_url": generated_voice.source_url,
                "message": generated_voice.message,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    generated_track: AudioTrack | None = None
    final_audio_mix: Path | None = None
    voice_mp3: Path | None = None
    voice_output_name = generated_voice.output_file or voice_filename
    voice_output_path = bundle_dir / voice_output_name
    if voice_output_path.exists() and voice_output_path.suffix.lower() == ".wav":
        try:
            voice_output_path = ensure_voice_duration(bundle_dir, voice_output_path, duration_minutes * 60)
        except (FileNotFoundError, subprocess.CalledProcessError, wave.Error, OSError):
            pass
    selected_music_path = generated_track.path if generated_track else (music.path if music else None)
    if selected_music_path and voice_output_path.exists() and voice_output_path.suffix.lower() == ".wav":
        final_audio_mix = create_final_audio_mix(bundle_dir, voice_output_path, selected_music_path)
    elif voice_output_path.exists() and voice_output_path.suffix.lower() == ".wav":
        voice_mp3 = convert_voice_wav_to_mp3(bundle_dir, voice_output_path)
    (bundle_dir / "剪映导入说明.md").write_text(
        build_jianying_notes(
            bundle_dir.name,
            generated_image.output_file or "cover.svg",
            generated_music.output_file or (music.path.name if music else None),
            generated_voice.output_file or voice_filename,
        ),
        encoding="utf-8",
    )

    if generated_music.output_file:
        generated_path = bundle_dir / generated_music.output_file
        generated_duration = safe_get_audio_duration(generated_path)
        generated_track = AudioTrack(
            path=generated_path,
            duration_seconds=generated_duration or 0.0,
            tags=normalize_tags(theme.get("music_tags", [])),
            selection_reason=f"generated_via_{generated_music.provider}",
        )

    manifest = {
        "date": target_date.isoformat(),
        "title": script["title"],
        "subtitle": script["subtitle"],
        "meditation_traditions": script.get("traditions", []),
        "channel_name": config.get("channel_name", ""),
        "duration_minutes": duration_minutes,
        "music_source": str((generated_track or music).path) if (generated_track or music) else None,
        "music_duration_hms": format_hms((generated_track or music).duration_seconds) if (generated_track or music) else None,
        "music_tags": (generated_track or music).tags if (generated_track or music) else normalize_tags(theme.get("music_tags", [])),
        "music_selection_reason": (generated_track or music).selection_reason if (generated_track or music) else "music_missing",
        "music_generation_status": generated_music.status,
        "music_generation_message": generated_music.message,
        "voice_provider": config.get("voice_clone", {}).get("provider"),
        "voice_generation_status": generated_voice.status,
        "voice_generation_message": generated_voice.message,
        "image_generation_status": generated_image.status,
        "image_generation_message": generated_image.message,
        "category": theme.get("category", "Sleep Meditation"),
        "files": {
            "cover": generated_image.output_file or "cover.svg",
            "fallback_cover": "cover.svg",
            "image_prompt": "image_prompt.txt",
            "image_request": "image_request.json",
            "image_generation_result": "image_generation_result.json",
            "music_prompt": "music_prompt.txt",
            "music_request": "music_request.json",
            "music_generation_result": "music_generation_result.json",
            "voice_script": "voiceover_script.txt",
            "voice_request": "voiceover_request.json",
            "voice_generation_result": "voice_generation_result.json",
            "voice_audio_expected": generated_voice.output_file or voice_filename,
            "voice_audio_mp3": voice_mp3.name if voice_mp3 else None,
            "final_audio_mix": final_audio_mix.name if final_audio_mix else None,
            "captions": "captions.srt",
        },
    }
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if music and not generated_track:
        shutil.copy2(music.path, bundle_dir / music.path.name)

    return bundle_dir


def update_state(root: Path, target_date: date, bundle_dir: Path, title: str) -> None:
    state_path = root / "state" / "generation_log.json"
    payload = load_json(state_path, [])
    manifest = load_json(bundle_dir / "bundle_manifest.json", {})
    music_source = str(manifest.get("music_source", "")).strip()
    music_filename = Path(music_source).name if music_source else None
    payload.append(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "date": target_date.isoformat(),
            "title": title,
            "music_filename": music_filename,
            "bundle_dir": str(bundle_dir),
        }
    )
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def first_matching_name(available_names: set[str], candidates: list[str]) -> str | None:
    for name in candidates:
        if name and name in available_names:
            return name
    return None


def infer_media_paths(bundle_dir: Path, manifest: dict) -> tuple[str | None, str | None, str]:
    files = manifest.get("files", {})
    available_names = {path.name for path in bundle_dir.iterdir() if path.is_file()}
    sorted_names = sorted(available_names)
    poster_name = first_matching_name(
        available_names,
        [
            str(files.get("cover", "")).strip(),
            str(files.get("fallback_cover", "")).strip(),
            "cover.svg",
            "cover.svg.png",
        ],
    )
    audio_name = first_matching_name(
        available_names,
        [
            str(files.get("final_audio_mix", "")).strip(),
            str(files.get("voice_audio_mp3", "")).strip(),
            Path(str(manifest.get("music_source", "")).strip()).name if manifest.get("music_source") else "",
            "0208 (1).MP3",
            "0208 (1).mp3",
            "voiceover.mp3",
            str(files.get("voice_audio_expected", "")).strip(),
        ],
    )
    if not audio_name:
        audio_name = next((name for name in sorted_names if name.lower().endswith(".mp3")), None)
    return audio_name, poster_name, "audio"


def is_modern_voice_only_bundle(bundle_dir: Path, manifest: dict) -> bool:
    files = manifest.get("files", {}) if isinstance(manifest.get("files"), dict) else {}
    raw_voice_mp3 = files.get("voice_audio_mp3")
    raw_final_mix = files.get("final_audio_mix")
    voice_mp3 = "" if raw_voice_mp3 is None else str(raw_voice_mp3).strip().lower()
    final_mix = "" if raw_final_mix is None else str(raw_final_mix).strip().lower()
    raw_music_source = manifest.get("music_source")
    music_source = "" if raw_music_source is None else str(raw_music_source).strip()
    if voice_mp3 == "voiceover.mp3" and not final_mix and not music_source:
        return True
    return False


def pick_cover_theme(title: str) -> str:
    lowered = title.lower()
    if "雨" in title:
        return "rain-cover"
    if "清晨" in title or "晨" in title:
        return "dawn-cover"
    if "情绪" in title or "舒缓" in title:
        return "dusk-cover"
    if "睡" in title or "night" in lowered or "sleep" in lowered:
        return "warm-cover"
    return "warm-cover"


def infer_title_from_bundle_dir(bundle_dir: Path) -> str:
    value = bundle_dir.name
    value = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", value)
    value = re.sub(r"-\d+$", "", value)
    title = value.strip() or bundle_dir.name
    translations = {
        "睡前释放": "Sleep Release",
        "情绪舒缓": "Emotional Ease",
        "专注回归": "Return to Focus",
        "清晨安定": "Morning Stillness",
        "雨夜归心": "Return Home on a Rainy Night",
        "深度放松": "Deep Relaxation",
        "夜间安睡": "Night Rest",
    }
    if title in translations:
        return translations[title]
    if "-" in title:
        return title.replace("-", " ").title()
    return title


def infer_subtitle_from_title(title: str) -> str:
    if "Rain" in title:
        return "A rain-soaked session to help you settle back into yourself and into sleep."
    if "Morning" in title:
        return "Ideal for falling back asleep after waking in the night, or for meeting the morning gently."
    if "Emotional" in title:
        return "Let emotion and breath slow down together as your mind returns to the body."
    if "Focus" in title:
        return "Gather scattered attention and return to a calmer, steadier inner pace."
    if "Sleep" in title:
        return "Loosen the weight of the day and let sleep come back naturally."
    return "A gentle guided meditation to help your body relax and your mind soften into sleep."


def build_session_subtitle(title: str, manifest: dict) -> str:
    manifest_subtitle = str(manifest.get("subtitle", "")).strip()
    if manifest_subtitle:
        return manifest_subtitle
    return infer_subtitle_from_title(title)


def build_session_description(title: str, subtitle: str, traditions: list[dict], kind: str, manifest: dict | None = None) -> str:
    manifest = manifest or {}
    tradition_names = [str(item.get("name", "")).strip() for item in traditions if str(item.get("name", "")).strip()]
    lowered_title = title.lower()

    if "quiet room" in lowered_title:
        return (
            "A quieter, more spacious sleep session for nights that feel mentally full. "
            "Built around simple presence and a softer, Zen-shaped way of letting thought pass without following it."
        )
    if "after the mind lets go" in lowered_title:
        return (
            "A calming sleep session for nights of overthinking, with softer breath guidance and a clearer path out of mental looping. "
            "Made for the kind of bedtime when the body is ready, but the mind has not yet learned how to let go."
        )
    if "still waters" in lowered_title:
        return (
            "A deeply unwinding sleep meditation with a steady human voice, slower exhales, and long settling pauses. "
            "Made for nights when the body is tired but the mind is still gently moving."
        )

    if tradition_names:
        joined = ", ".join(tradition_names[:3])
        if kind == "video":
            return f"{subtitle} Built around {joined}, it is ideal for nights when visual presence helps you settle."
        return f"{subtitle} Built around {joined}, it is ideal for closing your eyes and easing gradually into rest."
    if kind == "video":
        return f"{subtitle} Best for slowing down before bed through image, sound, and steady pacing."
    return f"{subtitle} Best played in a quiet room while your breathing and body gradually soften."


def normalize_media_base_url(config: dict) -> str:
    publishing = config.get("publishing", {}) if isinstance(config.get("publishing"), dict) else {}
    return str(publishing.get("media_base_url", "")).strip().rstrip("/")


def build_public_asset_url(media_base_url: str, bundle_name: str, asset_name: str | None) -> str | None:
    if not media_base_url or not asset_name:
        return None
    return f"{media_base_url}/{parse.quote(bundle_name)}/{parse.quote(asset_name)}"


def sync_website_library(root: Path, config: dict, only_bundle_names: set[str] | None = None) -> Path | None:
    website_dir = root / "website"
    if not website_dir.exists():
        return None

    bundle_dirs = sorted([path for path in (root / "output").iterdir() if path.is_dir()], reverse=True)
    sessions = []
    media_base_url = normalize_media_base_url(config)
    seen_titles: set[str] = set()

    for bundle_dir in bundle_dirs:
        if only_bundle_names and bundle_dir.name not in only_bundle_names:
            continue
        title = infer_title_from_bundle_dir(bundle_dir)
        normalized_title = title.strip().lower()
        if normalized_title in seen_titles:
            continue
        manifest = load_json(bundle_dir / "bundle_manifest.json", {})
        if not is_modern_voice_only_bundle(bundle_dir, manifest):
            continue
        subtitle = build_session_subtitle(title, manifest)
        media_name, poster_name, kind = infer_media_paths(bundle_dir, manifest)
        if not media_name:
            continue
        seen_titles.add(normalized_title)

        category = str(manifest.get("category", "Sleep Meditation")).strip() or "Sleep Meditation"
        meta_parts = [category]
        if "Morning" in title:
            meta_parts.append("Fall Back Asleep")
        elif "Emotional" in title:
            meta_parts.append("Emotional Release")
        elif "Focus" in title:
            meta_parts.append("Mental Reset")
        elif "Rain" in title:
            meta_parts.append("Rainy Night Atmosphere")
        elif "Sleep" in title:
            meta_parts.append("Sleep Relaxation")

        sessions.append(
            {
                "slug": bundle_dir.name,
                "date": bundle_dir.name[:10],
                "title": title,
                "subtitle": subtitle,
                "kind": "audio",
                "kindLabel": "Audio Session",
                "meta": " · ".join(meta_parts),
                "description": build_session_description(title, subtitle, [], "audio", manifest),
                "mediaPath": f"../output/{bundle_dir.name}/{parse.quote(media_name)}",
                "publicMediaPath": build_public_asset_url(media_base_url, bundle_dir.name, media_name),
                "posterPath": f"../output/{bundle_dir.name}/{parse.quote(poster_name)}" if poster_name else None,
                "publicPosterPath": build_public_asset_url(media_base_url, bundle_dir.name, poster_name),
                "coverTheme": pick_cover_theme(title),
            }
        )

    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "session_count": len(sessions),
        "sessions": sessions,
    }
    json_path = website_dir / "sessions.json"
    js_path = website_dir / "sessions.js"
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(serialized + "\n", encoding="utf-8")
    js_path.write_text(f"window.SESSION_LIBRARY = {serialized};\n", encoding="utf-8")
    return json_path


def sync_netlify_publish_dir(root: Path, config: dict) -> Path | None:
    website_dir = root / "website"
    sessions_path = website_dir / "sessions.json"
    if not website_dir.exists() or not sessions_path.exists():
        return None

    payload = load_json(sessions_path, {})
    sessions = payload.get("sessions", []) if isinstance(payload.get("sessions"), list) else []
    publishing = config.get("publishing", {}) if isinstance(config.get("publishing"), dict) else {}
    copy_media_to_deploy = bool(publishing.get("copy_media_to_deploy", True))
    media_base_url = normalize_media_base_url(config)
    deploy_dir = root / "deploy" / "netlify-site"
    deploy_output_dir = deploy_dir / "output"

    deploy_dir.mkdir(parents=True, exist_ok=True)
    if deploy_output_dir.exists():
        shutil.rmtree(deploy_output_dir)
    deploy_output_dir.mkdir(parents=True, exist_ok=True)

    for filename in ["index.html", "styles.css", "app.js", "site-config.js", "sessions.js", "sessions.json"]:
        source = website_dir / filename
        if source.exists():
            shutil.copy2(source, deploy_dir / filename)

    copied_bundles: set[str] = set()
    if copy_media_to_deploy:
        for session in sessions:
            media_path = str(session.get("mediaPath", "")).strip()
            poster_path = str(session.get("posterPath", "")).strip()
            referenced_paths = [path for path in [media_path, poster_path] if path]
            for relative_path in referenced_paths:
                normalized = parse.unquote(relative_path.replace("../output/", ""))
                parts = Path(normalized).parts
                if len(parts) < 2:
                    continue
                bundle_name = parts[0]
                bundle_target_dir = deploy_output_dir / bundle_name
                bundle_target_dir.mkdir(parents=True, exist_ok=True)
                source_file = root / "output" / bundle_name / parts[-1]
                if source_file.exists():
                    shutil.copy2(source_file, bundle_target_dir / parts[-1])
                    copied_bundles.add(bundle_name)

    for filename in ["index.html", "sessions.js", "sessions.json"]:
        target_path = deploy_dir / filename
        if target_path.exists():
            target_path.write_text(
                target_path.read_text(encoding="utf-8").replace("../output/", "./output/"),
                encoding="utf-8",
            )

    readme_path = deploy_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "come to sleep by Leo Chan",
                "",
                "This folder is the ready-to-upload Netlify package.",
                "",
                "How it updates:",
                "- Every time `daily_meditation_pipeline.py` generates a new session, this folder is refreshed automatically.",
                "- Netlify should use this folder as the publish directory.",
                f"- External media base URL: {media_base_url or 'not set'}",
                f"- Copy media into deploy output: {'yes' if copy_media_to_deploy else 'no'}",
                "",
                "Recommended Netlify setup:",
                "- Build command: leave empty",
                "- Publish directory: deploy/netlify-site",
                "",
                "Current bundles included:",
                *[f"- {bundle_name}" for bundle_name in sorted(copied_bundles)],
                "",
                "Important:",
                "- Replace `hello@example.com` before public launch.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    netlify_toml = root / "netlify.toml"
    netlify_toml.write_text(
        "\n".join(
            [
                "[build]",
                '  publish = "deploy/netlify-site"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    return deploy_dir


def sync_cloudflare_publish_dir(root: Path) -> Path | None:
    netlify_dir = root / "deploy" / "netlify-site"
    if not netlify_dir.exists():
        return None

    cloudflare_dir = root / "deploy" / "cloudflare-pages"
    if cloudflare_dir.exists():
        shutil.rmtree(cloudflare_dir)
    shutil.copytree(netlify_dir, cloudflare_dir)

    readme_path = cloudflare_dir / "README.md"
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
        content = content.replace("ready-to-upload Netlify package", "ready-to-upload Cloudflare Pages package")
        content = content.replace("- Netlify should use this folder as the publish directory.", "- Cloudflare Pages can use this folder for direct upload.")
        content = content.replace("Recommended Netlify setup:", "Recommended Cloudflare Pages setup:")
        content = content.replace("- Publish directory: deploy/netlify-site", "- Build output directory: deploy/netlify-site")
        readme_path.write_text(content, encoding="utf-8")

    return cloudflare_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成每日冥想视频素材包，供剪映专业版导入。")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录。")
    parser.add_argument("--date", type=str, default=None, help="目标日期，格式 YYYY-MM-DD。默认今天。")
    parser.add_argument("--bootstrap-only", action="store_true", help="只初始化项目文件，不生成当日素材。")
    parser.add_argument("--theme-name", type=str, default=None, help="指定主题名。")
    parser.add_argument("--website-single-latest", action="store_true", help="网站只同步本次生成的单条内容。")
    parser.add_argument("--duration-minutes", type=int, default=None, help="指定生成时长（分钟）。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    bootstrap_files(root)
    if args.bootstrap_only:
        print(f"Initialized project files under: {root}")
        return 0

    target_date = date.fromisoformat(args.date) if args.date else datetime.now().date()
    config = merge_dict(DEFAULT_CONFIG, load_json(root / "config" / "project_config.json", DEFAULT_CONFIG))
    themes = load_json(root / "config" / "theme_library.json", DEFAULT_THEMES)
    theme = choose_theme_by_name(themes, args.theme_name) if args.theme_name else choose_theme(themes, target_date)
    music = choose_music(root, config, theme, target_date)
    bundle_dir = write_bundle(root, target_date, config, theme, music, forced_duration_minutes=args.duration_minutes)
    update_state(root, target_date, bundle_dir, theme["name"])
    sessions_path = sync_website_library(root, config, {bundle_dir.name} if args.website_single_latest else None)
    deploy_path = sync_netlify_publish_dir(root, config)
    cloudflare_path = sync_cloudflare_publish_dir(root)

    print(f"Created daily meditation bundle: {bundle_dir}")
    print(f"Theme: {theme['name']}")
    if music:
        print(f"Music: {music.path.name} ({format_hms(music.duration_seconds)})")
    else:
        print("Music: not found. Please add music files into assets/music.")
    print(f"Voice request: {bundle_dir / 'voiceover_request.json'}")
    if sessions_path:
        print(f"Website library synced: {sessions_path}")
    if deploy_path:
        print(f"Netlify publish dir synced: {deploy_path}")
    if cloudflare_path:
        print(f"Cloudflare Pages package synced: {cloudflare_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
