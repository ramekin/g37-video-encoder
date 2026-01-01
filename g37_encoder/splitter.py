"""Split pre-encoded video files to fit G37x file size limits."""

import math
import subprocess
import sys
from pathlib import Path

from .utils import get_media_info, find_chapter_split_points


MAX_FILE_SIZE_BYTES = 1900 * 1024 * 1024  # 1900MB, margin under 2GB


def calculate_parts_needed(duration: float, bitrate: int, max_bytes: int = MAX_FILE_SIZE_BYTES) -> int:
    """Calculate how many parts are needed based on actual bitrate."""
    if bitrate <= 0:
        raise ValueError("Invalid bitrate")

    # max_seconds = max_bytes * 8 / bitrate
    max_segment_duration = (max_bytes * 8) / bitrate

    return math.ceil(duration / max_segment_duration)


def split_encoded_file(
    encoded_file: Path,
    source_file: Path | None = None,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    verbose: bool = True,
) -> list[Path]:
    """
    Split an already-encoded video file into parts under the size limit.

    Uses stream copy (no re-encoding) for fast splitting.

    Args:
        encoded_file: The encoded video file to split
        source_file: Optional source file with chapters (for chapter-aware splitting)
        max_size_bytes: Maximum size per output file in bytes
        verbose: Print progress information

    Returns:
        List of output file paths
    """
    encoded_file = Path(encoded_file)
    if not encoded_file.exists():
        raise FileNotFoundError(f"Encoded file not found: {encoded_file}")

    # Get info about the encoded file
    encoded_info = get_media_info(encoded_file)
    duration = encoded_info.duration
    bitrate = encoded_info.bitrate

    if bitrate <= 0:
        raise ValueError(f"Could not determine bitrate of {encoded_file}")

    if verbose:
        print(f"Encoded file: {encoded_file}")
        print(f"Duration: {duration:.1f}s ({duration/60:.1f} min)")
        print(f"Bitrate: {bitrate / 1000:.0f} kbps")
        file_size_mb = encoded_file.stat().st_size / (1024 * 1024)
        print(f"File size: {file_size_mb:.0f}MB")

    # Check if splitting is needed
    if encoded_file.stat().st_size <= max_size_bytes:
        if verbose:
            print("File is already under size limit, no splitting needed.")
        return [encoded_file]

    # Calculate number of parts needed
    num_parts = calculate_parts_needed(duration, bitrate, max_size_bytes)

    if verbose:
        max_mb = max_size_bytes / (1024 * 1024)
        print(f"Need to split into {num_parts} parts (max {max_mb:.0f}MB each)")

    # Get chapters from source file if provided
    chapters = []
    if source_file:
        source_file = Path(source_file)
        if source_file.exists():
            source_info = get_media_info(source_file)
            chapters = source_info.chapters
            if verbose and chapters:
                print(f"Found {len(chapters)} chapters in source file")

    # Determine split points
    split_points = find_chapter_split_points(chapters, duration, num_parts)

    if verbose:
        print(f"Split points: {[f'{t:.1f}s' for t in split_points]}")
        if chapters:
            for point in split_points:
                # Find matching chapter
                for ch in chapters:
                    if abs(ch.start_time - point) < 0.1:
                        print(f"  {point:.1f}s = Chapter: {ch.title}")
                        break

    # Generate output filenames
    base = encoded_file.stem
    ext = encoded_file.suffix
    output_dir = encoded_file.parent

    # Split the file
    output_files = []
    segments = _create_segments(duration, split_points)

    for i, (start, end) in enumerate(segments, 1):
        part_file = output_dir / f"{base}_part{i}{ext}"
        output_files.append(part_file)

        if verbose:
            print(f"\n=== Splitting Part {i}/{len(segments)} ===")
            print(f"  Time range: {start:.1f}s - {end:.1f}s")

        cmd = ["ffmpeg", "-i", str(encoded_file)]

        if start > 0:
            cmd.extend(["-ss", str(start)])

        segment_duration = end - start
        cmd.extend(["-t", str(segment_duration)])

        # Copy streams without re-encoding
        cmd.extend(["-c", "copy", str(part_file)])

        _run_ffmpeg(cmd, verbose)

    if verbose:
        print(f"\nSplit complete:")
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
    subprocess.run(cmd, check=True,
                   stdout=sys.stdout if verbose else subprocess.DEVNULL,
                   stderr=sys.stderr if verbose else subprocess.DEVNULL)
