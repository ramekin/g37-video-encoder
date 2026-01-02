"""Video encoder for G37x compatibility."""

import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .utils import (
    get_media_info,
    estimate_output_size_mb,
    find_chapter_split_points,
)


# G37x compatible encoding settings
DEFAULT_VIDEO_BITRATE_KBPS = 2500
DEFAULT_AUDIO_BITRATE_KBPS = 320
MAX_FILE_SIZE_MB = 1900  # Leave margin under 2GB FAT32 limit


@dataclass
class EncodingConfig:
    """Configuration for video encoding."""
    video_bitrate_kbps: int = DEFAULT_VIDEO_BITRATE_KBPS
    audio_bitrate_kbps: int = DEFAULT_AUDIO_BITRATE_KBPS
    width: int = 720
    height: int = 480
    framerate: int = 24
    audio_channels: int = 2
    audio_sample_rate: int = 48000
    max_file_size_mb: int = MAX_FILE_SIZE_MB


def build_ffmpeg_command(
    input_file: Path,
    output_file: Path,
    config: EncodingConfig,
    start_time: float | None = None,
    end_time: float | None = None,
) -> list[str]:
    """Build ffmpeg command for G37x compatible encoding."""
    cmd = ["ffmpeg", "-loglevel", "error", "-i", str(input_file)]

    # Time range options
    if start_time is not None:
        cmd.extend(["-ss", str(start_time)])
    if end_time is not None:
        cmd.extend(["-to", str(end_time)])

    # Video encoding options (MPEG4 with DX50 tag for DivX compatibility)
    cmd.extend([
        "-c:v", "mpeg4",
        "-vtag", "DX50",
        "-s", f"{config.width}x{config.height}",
        "-r", str(config.framerate),
        "-b:v", f"{config.video_bitrate_kbps}k",
        # Enforce target bitrate (mpeg4 encoder tends to undershoot with VBR)
        "-minrate", f"{config.video_bitrate_kbps}k",
        "-maxrate", f"{config.video_bitrate_kbps}k",
        "-bufsize", f"{config.video_bitrate_kbps}k",
    ])

    # Audio encoding options (MP3)
    cmd.extend([
        "-c:a", "libmp3lame",
        "-b:a", f"{config.audio_bitrate_kbps}k",
        "-ac", str(config.audio_channels),
        "-ar", str(config.audio_sample_rate),
    ])

    cmd.append(str(output_file))
    return cmd


def calculate_num_parts(duration: float, config: EncodingConfig) -> int:
    """Calculate how many parts the output will need to be split into."""
    estimated_size = estimate_output_size_mb(
        duration,
        config.video_bitrate_kbps,
        config.audio_bitrate_kbps
    )
    if estimated_size <= config.max_file_size_mb:
        return 1
    return math.ceil(estimated_size / config.max_file_size_mb)


def encode_video(
    input_file: Path,
    output_file: Path,
    config: EncodingConfig | None = None,
    verbose: bool = True,
) -> list[Path]:
    """
    Encode a video file for G37x compatibility.

    Automatically splits output if it would exceed the max file size,
    preferring chapter boundaries for split points.

    Returns list of output file paths.
    """
    if config is None:
        config = EncodingConfig()

    input_file = Path(input_file)
    output_file = Path(output_file)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Get media information
    media_info = get_media_info(input_file)
    duration = media_info.duration

    if verbose:
        print(f"Input file: {input_file}")
        print(f"Duration: {duration:.1f}s ({duration/60:.1f} min)")
        print(f"Video bitrate: {config.video_bitrate_kbps}k")
        print(f"Audio bitrate: {config.audio_bitrate_kbps}k")

    # Calculate number of parts needed
    num_parts = calculate_num_parts(duration, config)
    estimated_total = estimate_output_size_mb(
        duration,
        config.video_bitrate_kbps,
        config.audio_bitrate_kbps
    )

    if verbose:
        print(f"Estimated total size: {estimated_total:.0f}MB")
        if num_parts > 1:
            print(f"Will split into {num_parts} parts (max {config.max_file_size_mb}MB each)")

    output_files = []

    if num_parts == 1:
        # Single file output
        if verbose:
            print(f"\n=== Encoding ===")
        cmd = build_ffmpeg_command(input_file, output_file, config)
        _run_ffmpeg(cmd, verbose)
        output_files.append(output_file)
    else:
        # Multi-part output
        split_points = find_chapter_split_points(
            media_info.chapters,
            duration,
            num_parts
        )

        if verbose:
            if media_info.chapters:
                print(f"Found {len(media_info.chapters)} chapters")
            print(f"Split points: {[f'{t:.1f}s' for t in split_points]}")

        # Generate output filenames
        base = output_file.stem
        ext = output_file.suffix

        # Encode each segment
        segments = _create_segments(duration, split_points)
        for i, (start, end) in enumerate(segments, 1):
            part_file = output_file.parent / f"{base}_part{i}{ext}"
            output_files.append(part_file)

            if verbose:
                print(f"\n=== Encoding Part {i}/{len(segments)} ===")
                print(f"  Time range: {start:.1f}s - {end:.1f}s")

            cmd = build_ffmpeg_command(
                input_file, part_file, config,
                start_time=start if start > 0 else None,
                end_time=end if end < duration else None
            )
            _run_ffmpeg(cmd, verbose)

    if verbose:
        print(f"\nConversion complete:")
        for f in output_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  {f} ({size_mb:.0f}MB)")

    return output_files


def _create_segments(duration: float, split_points: list[float]) -> list[tuple[float, float]]:
    """Create list of (start, end) tuples for each segment."""
    segments = []
    prev = 0.0
    for point in split_points:
        segments.append((prev, point))
        prev = point
    segments.append((prev, duration))
    return segments


def _run_ffmpeg(cmd: list[str], verbose: bool) -> None:
    """Run ffmpeg command."""
    if verbose:
        print(f"  Running: {' '.join(cmd[:6])}...")
    subprocess.run(cmd, check=True, stdout=sys.stdout if verbose else subprocess.DEVNULL,
                   stderr=sys.stderr if verbose else subprocess.DEVNULL)
