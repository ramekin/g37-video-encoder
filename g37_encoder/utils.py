"""Utility functions for ffprobe operations."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chapter:
    """Represents a video chapter."""
    start_time: float
    end_time: float
    title: str


@dataclass
class MediaInfo:
    """Information about a media file."""
    duration: float
    bitrate: int  # bits per second
    chapters: list[Chapter]


def run_ffprobe(args: list[str]) -> str:
    """Run ffprobe with given arguments and return stdout."""
    cmd = ["ffprobe", "-v", "quiet"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def get_duration(file_path: Path) -> float:
    """Get duration of a media file in seconds."""
    output = run_ffprobe([
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(file_path)
    ])
    return float(output.strip())


def get_bitrate(file_path: Path) -> int:
    """Get bitrate of a media file in bits per second."""
    output = run_ffprobe([
        "-show_entries", "format=bit_rate",
        "-of", "csv=p=0",
        str(file_path)
    ])
    return int(output.strip())


def get_chapters(file_path: Path) -> list[Chapter]:
    """Get chapters from a media file."""
    output = run_ffprobe([
        "-print_format", "json",
        "-show_chapters",
        str(file_path)
    ])
    data = json.loads(output)
    chapters = []
    for ch in data.get("chapters", []):
        chapters.append(Chapter(
            start_time=float(ch["start_time"]),
            end_time=float(ch["end_time"]),
            title=ch.get("tags", {}).get("title", "Unknown")
        ))
    return chapters


def get_media_info(file_path: Path) -> MediaInfo:
    """Get complete media information."""
    output = run_ffprobe([
        "-print_format", "json",
        "-show_format",
        "-show_chapters",
        str(file_path)
    ])
    data = json.loads(output)

    format_info = data.get("format", {})
    duration = float(format_info.get("duration", 0))
    bitrate = int(format_info.get("bit_rate", 0))

    chapters = []
    for ch in data.get("chapters", []):
        chapters.append(Chapter(
            start_time=float(ch["start_time"]),
            end_time=float(ch["end_time"]),
            title=ch.get("tags", {}).get("title", "Unknown")
        ))

    return MediaInfo(duration=duration, bitrate=bitrate, chapters=chapters)


def find_chapter_split_points(chapters: list[Chapter], duration: float, num_parts: int) -> list[float]:
    """
    Find optimal chapter boundaries to split video into N parts.

    Returns a list of split times (chapter start times) that divide
    the video as evenly as possible.
    """
    if not chapters or num_parts <= 1:
        # No chapters: split evenly by time
        return [duration * i / num_parts for i in range(1, num_parts)]

    chapter_starts = [ch.start_time for ch in chapters]
    target_segment_duration = duration / num_parts

    split_points = []
    for i in range(1, num_parts):
        target_time = target_segment_duration * i
        # Find chapter start closest to target
        closest = min(chapter_starts, key=lambda t: abs(t - target_time))
        # Avoid duplicate split points
        if closest not in split_points and closest > 0:
            split_points.append(closest)

    # Sort and ensure we have valid split points
    split_points = sorted(set(split_points))

    # If we couldn't find enough chapter boundaries, fall back to even splits
    if len(split_points) < num_parts - 1:
        return [duration * i / num_parts for i in range(1, num_parts)]

    return split_points[:num_parts - 1]


def estimate_output_size_mb(duration_seconds: float, video_kbps: int, audio_kbps: int) -> float:
    """Estimate output file size in MB."""
    total_kbps = video_kbps + audio_kbps
    return (total_kbps * duration_seconds) / 8 / 1024
