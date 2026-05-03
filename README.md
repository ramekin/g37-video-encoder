# G37x Video Encoder

Encode videos for playback on the 2012 Infiniti G37x with Navigation system.

## Features

- Encodes videos to G37x-compatible format (MPEG4/DivX in AVI container)
- Automatically splits large files to stay under the 2GB FAT32 limit
- Three split modes: auto (size + chapter alignment), chapter (one per chapter), size (even)
- VBR (default) or CBR encoding modes
- Selects English audio track automatically
- Can split already-encoded files without re-encoding

## Requirements

- Python 3.10+
- FFmpeg with libmp3lame support
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### Using uv (recommended)

Install globally (adds `g37-encode` to PATH):

```bash
uv tool install git+https://github.com/ramekin/g37-video-encoder
```

Or run directly without installing:

```bash
uvx --from git+https://github.com/ramekin/g37-video-encoder g37-encode video.mkv output.avi
```

For local development (from repo directory):

```bash
uv run g37-encode video.mkv output.avi
```

### Using pip

```bash
pip install -e .
```

## Usage

### Encode a video

```bash
g37-encode video.mkv output.avi
```

### Encode with custom bitrate

```bash
g37-encode video.mkv output.avi --video-bitrate 3000
```

### Split an already-encoded file

If you have a file that's already encoded but too large:

```bash
g37-encode --split encoded.avi
```

### Split using chapters from source

For chapter-aware splitting of pre-encoded files:

```bash
g37-encode --split encoded.avi --source-chapters original.mkv
```

### Split into one file per chapter

```bash
g37-encode video.mkv output.avi --split-mode chapter
```

Or for a pre-encoded file:

```bash
g37-encode --split encoded.avi --source-chapters original.mkv --split-mode chapter
```

## Split Modes

| Mode | Behavior |
|------|----------|
| `auto` (default) | Split by file size, snap to nearest chapter boundary |
| `chapter` | One file per chapter (always splits, ignores size limit) |
| `size` | Split evenly by file size, ignore chapters |

## Encoding Modes

| Mode | Behavior |
|------|----------|
| VBR (default) | Encode whole file, split after if over size limit |
| CBR (`--cbr`) | Force target bitrate, pre-split during encoding |

## Output Format

The encoder produces files with these specifications:

| Setting | Value |
|---------|-------|
| Video Codec | MPEG4 (DivX/DX50) |
| Resolution | 720x480 |
| Frame Rate | 24 fps |
| Video Bitrate | 2500 kbps (default) |
| Audio Codec | MP3 |
| Audio Bitrate | 320 kbps |
| Audio Channels | Stereo |
| Sample Rate | 48 kHz |
| Container | AVI |
| Max File Size | 1900 MB |

## Command Reference

Run `g37-encode --help` for the full list of options.

## License

MIT
