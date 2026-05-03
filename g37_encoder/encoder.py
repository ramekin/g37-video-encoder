"""Video encoder for G37x compatibility."""

import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .utils import (
    get_media_info,
    estimate_output_size_mb,
    compute_split_points,
    SPLIT_MODE_AUTO,
    SPLIT_MODE_CHAPTER,
    SPLIT_MODE_SIZE,
)
from .splitter import split_encoded_file


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
    cbr: bool = False  # Use constant bitrate (forces target bitrate)
    split_mode: str = SPLIT_MODE_AUTO  # chapter, size, or auto


def build_ffmpeg_command(
    input_file: Path,
    output_file: Path,
    config: EncodingConfig,
    start_time: float | None = None,
    end_time: float | None = None,
) -> list[str]:
    """Build ffmpeg command for G37x compatible encoding."""
    cmd = ["ffmpeg", "-loglevel", "error", "-stats", "-i", str(input_file)]

    # Stream mapping: select first video and English audio
    cmd.extend([
        "-map", "0:v:0",              # First video stream
        "-map", "0:a:m:language:eng", # English audio stream
    ])

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
    ])

    # CBR mode: enforce target bitrate strictly
    if config.cbr:
        cmd.extend([
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

    With CBR mode: estimates size upfront and splits during encoding.
    With VBR mode (default): encodes whole file, then splits if needed.

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
        print(f"Mode: {'CBR' if config.cbr else 'VBR'}")

    if config.cbr:
        # CBR mode: estimate size and pre-split during encoding
        return _encode_cbr(input_file, output_file, config, media_info, verbose)
    else:
        # VBR mode: encode whole file, then split if needed
        return _encode_vbr(input_file, output_file, config, media_info, verbose)


def _encode_cbr(
    input_file: Path,
    output_file: Path,
    config: EncodingConfig,
    media_info,
    verbose: bool,
) -> list[Path]:
    """Encode with CBR, pre-splitting based on split mode."""
    duration = media_info.duration
    estimated_total = estimate_output_size_mb(
        duration,
        config.video_bitrate_kbps,
        config.audio_bitrate_kbps
    )

    if verbose:
        print(f"Estimated total size: {estimated_total:.0f}MB")
        print(f"Split mode: {config.split_mode}")

    if config.split_mode == SPLIT_MODE_CHAPTER:
        # Always split by chapter
        split_points = compute_split_points(
            media_info.chapters, duration, 0, SPLIT_MODE_CHAPTER
        )
        if verbose:
            print(f"Splitting into {len(split_points) + 1} chapters")
    else:
        # size or auto: determine parts based on estimated size
        num_parts = calculate_num_parts(duration, config)
        if num_parts == 1:
            # Single file - no splitting needed
            if verbose:
                print(f"\n=== Encoding ===")
            cmd = build_ffmpeg_command(input_file, output_file, config)
            _run_ffmpeg(cmd, verbose)
            _print_completion([output_file], verbose)
            return [output_file]

        if verbose:
            print(f"Will split into {num_parts} parts (max {config.max_file_size_mb}MB each)")

        split_points = compute_split_points(
            media_info.chapters, duration, num_parts, config.split_mode
        )

    if verbose:
        if media_info.chapters:
            print(f"Found {len(media_info.chapters)} chapters")
        print(f"Split points: {[f'{t:.1f}s' for t in split_points]}")

    return _encode_segments(input_file, output_file, config, duration, split_points, verbose)


def _encode_segments(
    input_file: Path,
    output_file: Path,
    config: EncodingConfig,
    duration: float,
    split_points: list[float],
    verbose: bool,
) -> list[Path]:
    """Encode multiple segments based on split points."""
    base = output_file.stem
    ext = output_file.suffix
    output_files = []

    segments = _create_segments(duration, split_points)
    for i, (start, end) in enumerate(segments, 1):
        part_file = output_file.parent / f"{base}_part{i:03d}{ext}"
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

    _print_completion(output_files, verbose)
    return output_files


def _print_completion(output_files: list[Path], verbose: bool) -> None:
    """Print completion summary."""
    if not verbose:
        return
    print(f"\nConversion complete:")
    for f in output_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f} ({size_mb:.0f}MB)")


def _encode_vbr(
    input_file: Path,
    output_file: Path,
    config: EncodingConfig,
    media_info,
    verbose: bool,
) -> list[Path]:
    """Encode with VBR, splitting after based on split mode."""
    if verbose:
        print(f"Split mode: {config.split_mode}")

    # Validate chapter mode upfront before encoding
    if config.split_mode == SPLIT_MODE_CHAPTER and not media_info.chapters:
        raise ValueError("Cannot split by chapter: no chapters found in source")

    # Encode the whole file first
    if verbose:
        print(f"\n=== Encoding ===")
    cmd = build_ffmpeg_command(input_file, output_file, config)
    _run_ffmpeg(cmd, verbose)

    actual_size_bytes = output_file.stat().st_size
    actual_size_mb = actual_size_bytes / (1024 * 1024)
    max_size_bytes = config.max_file_size_mb * 1024 * 1024

    if verbose:
        print(f"\nEncoded file size: {actual_size_mb:.0f}MB")

    # Chapter mode: always split into chapters
    # Size/auto mode: only split if over limit
    if config.split_mode != SPLIT_MODE_CHAPTER and actual_size_bytes <= max_size_bytes:
        if verbose:
            print(f"\nConversion complete:")
            print(f"  {output_file} ({actual_size_mb:.0f}MB)")
        return [output_file]

    if verbose:
        if config.split_mode == SPLIT_MODE_CHAPTER:
            print(f"Splitting by chapter...")
        else:
            print(f"File exceeds {config.max_file_size_mb}MB limit, splitting...")

    split_files = split_encoded_file(
        encoded_file=output_file,
        source_file=input_file,
        max_size_bytes=max_size_bytes,
        split_mode=config.split_mode,
        verbose=verbose,
    )

    # Delete the original large file
    if verbose:
        print(f"\nRemoving original file: {output_file}")
    output_file.unlink()

    _print_completion(split_files, verbose)
    return split_files


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
