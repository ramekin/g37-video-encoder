# G37x Video Encoder

Encode videos for playback on the 2012 Infiniti G37x with Navigation system.

## Features

- Encodes videos to G37x-compatible format (MPEG4/DivX in AVI container)
- Automatically splits large files to stay under the 2GB FAT32 limit
- Prefers chapter boundaries for split points when available
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

```
usage: g37-encode [-h] [--version] [--split] [--video-bitrate KBPS]
                  [--audio-bitrate KBPS] [--max-size MB]
                  [--source-chapters FILE] [--quiet]
                  input [output]

positional arguments:
  input                 Input video file (or encoded file when using --split)
  output                Output file path (not used with --split)

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --split, -s           Split an already-encoded file instead of encoding
  --quiet, -q           Suppress progress output

encoding options:
  --video-bitrate KBPS, -vb KBPS
                        Video bitrate in kbps (default: 2500)
  --audio-bitrate KBPS, -ab KBPS
                        Audio bitrate in kbps (default: 320)
  --max-size MB, -m MB  Maximum file size in MB (default: 1900)

split options:
  --source-chapters FILE, -c FILE
                        Source file with chapters (for chapter-aware splitting)
```

## License

MIT
