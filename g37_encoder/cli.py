"""Command-line interface for G37x video encoder."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .encoder import EncodingConfig, encode_video, DEFAULT_VIDEO_BITRATE_KBPS, DEFAULT_AUDIO_BITRATE_KBPS
from .splitter import split_encoded_file, MAX_FILE_SIZE_BYTES
from .utils import SPLIT_MODES, SPLIT_MODE_AUTO


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="g37-encode",
        description="Encode videos for 2012 Infiniti G37x with Navigation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Encode a video:
    g37-encode video.mkv output.avi

  Encode with custom bitrate:
    g37-encode video.mkv output.avi --video-bitrate 3000

  Split an already-encoded file:
    g37-encode --split encoded.avi

  Split using chapters from source:
    g37-encode --split encoded.avi --source-chapters movie.mkv

  Split into one file per chapter:
    g37-encode video.mkv output.avi --split-mode chapter

Output format:
  - Video: MPEG4 (DivX/DX50 compatible), 720x480, 24fps
  - Audio: MP3, 320kbps, 48kHz stereo
  - Container: AVI
  - Files automatically split if they exceed 1900MB

Encoding modes:
  - VBR (default): Encodes whole file, then splits if needed. Lets encoder
    decide optimal bitrate - often produces smaller files at same quality.
  - CBR (--cbr): Forces target bitrate, pre-splits during encoding based on
    estimated size. Use for testing hardware bitrate limits.

Split modes:
  - auto (default): Split by file size, prefer chapter boundaries when possible.
  - chapter: One file per chapter (always splits, ignores size limit).
  - size: Split evenly by file size, ignore chapter boundaries.
"""
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--split", "-s",
        action="store_true",
        help="Split an already-encoded file instead of encoding"
    )

    # Input/output files
    parser.add_argument(
        "input",
        type=Path,
        help="Input video file (or encoded file when using --split)"
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output file path (not used with --split)"
    )

    # Encoding options
    encode_group = parser.add_argument_group("encoding options")
    encode_group.add_argument(
        "--video-bitrate", "-vb",
        type=int,
        default=DEFAULT_VIDEO_BITRATE_KBPS,
        metavar="KBPS",
        help=f"Video bitrate in kbps (default: {DEFAULT_VIDEO_BITRATE_KBPS})"
    )
    encode_group.add_argument(
        "--audio-bitrate", "-ab",
        type=int,
        default=DEFAULT_AUDIO_BITRATE_KBPS,
        metavar="KBPS",
        help=f"Audio bitrate in kbps (default: {DEFAULT_AUDIO_BITRATE_KBPS})"
    )
    encode_group.add_argument(
        "--audio-lang",
        default="eng",
        metavar="LANG",
        help="ISO 639-2 audio language code (default: eng). Examples: eng, spa, fra, deu, jpn"
    )
    encode_group.add_argument(
        "--max-size", "-m",
        type=int,
        default=1900,
        metavar="MB",
        help="Maximum file size in MB (default: 1900)"
    )
    encode_group.add_argument(
        "--cbr",
        action="store_true",
        help="Use constant bitrate (forces target bitrate, pre-splits during encoding)"
    )

    # Split options
    split_group = parser.add_argument_group("split options")
    split_group.add_argument(
        "--split-mode",
        choices=SPLIT_MODES,
        default=SPLIT_MODE_AUTO,
        help=f"How to split: chapter (per chapter), size (even), auto (size + chapter boundary). Default: {SPLIT_MODE_AUTO}"
    )
    split_group.add_argument(
        "--source-chapters", "-c",
        type=Path,
        metavar="FILE",
        help="Source file with chapters (for chapter-aware splitting in --split mode)"
    )

    # General options
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.split:
        # Split mode
        return cmd_split(args)
    else:
        # Encode mode
        if not args.output:
            parser.error("output file is required when encoding")
        return cmd_encode(args)


def cmd_encode(args) -> int:
    """Handle encode command."""
    config = EncodingConfig(
        video_bitrate_kbps=args.video_bitrate,
        audio_bitrate_kbps=args.audio_bitrate,
        max_file_size_mb=args.max_size,
        cbr=args.cbr,
        split_mode=args.split_mode,
        audio_language=args.audio_lang,
    )

    try:
        encode_video(
            input_file=args.input,
            output_file=args.output,
            config=config,
            verbose=not args.quiet,
        )
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during encoding: {e}", file=sys.stderr)
        return 1


def cmd_split(args) -> int:
    """Handle split command."""
    max_bytes = args.max_size * 1024 * 1024

    try:
        split_encoded_file(
            encoded_file=args.input,
            source_file=args.source_chapters,
            max_size_bytes=max_bytes,
            split_mode=args.split_mode,
            verbose=not args.quiet,
        )
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during splitting: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
