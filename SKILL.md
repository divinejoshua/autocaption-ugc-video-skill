---
name: autocaption-ugc-video
description: Use when the user wants to "add auto captions to video", "add captions to my video", "burn subtitles into video", "auto caption this video", or mentions adding text/subtitles to a local UGC video file. Triggers when a local video file path is provided and captions are requested.
version: 1.0.0
---

# Auto-Caption UGC Video Skill

Add burned-in, UGC-style captions to any local video using Whisper (speech-to-text) + FFmpeg. Captions are big, bold, and mobile-optimised — perfect for Reels, TikToks, and YouTube Shorts.

## Prerequisites

Install once, then forget:

```bash
# FFmpeg (video processing)
brew install ffmpeg          # macOS
# sudo apt install ffmpeg   # Ubuntu/Debian

# Whisper (speech-to-text)
pip install openai-whisper
```

Verify:
```bash
which ffmpeg && python3 -c "import whisper; print('whisper ok')"
```

## Quick Start

When the user provides a video file, run:

```bash
python3 ~/.claude/skills/autocaption-ugc-video/scripts/autocaption.py /path/to/video.mp4
```

Output is saved as `video_captioned.mp4` in the same folder as the input. That's it — no other arguments needed for standard UGC use.

## What It Does

1. **Transcribe** — Whisper listens to the video and generates word-level timestamps
2. **Build SRT** — Groups words into short 4-word chunks for punchy caption bursts
3. **Burn captions** — FFmpeg bakes the captions into the video using big, bold, white text with a black outline

## Caption Style (UGC defaults)

| Property     | Value              |
|--------------|--------------------|
| Font size    | 75px (big)         |
| Weight       | Bold               |
| Color        | White              |
| Outline      | Black, 3px         |
| Position     | Bottom-center      |
| Words/line   | 4                  |

These are tuned for social media — large enough to read while scrolling.

## Common Customisations

```bash
# Larger text
python3 autocaption.py video.mp4 --font-size 90

# Yellow text (great on dark footage)
python3 autocaption.py video.mp4 --font-color yellow

# More accurate transcription (slower)
python3 autocaption.py video.mp4 --model small

# Specify output path
python3 autocaption.py video.mp4 -o ~/Desktop/final_captioned.mp4

# Keep the SRT file (for editing in CapCut / Premiere)
python3 autocaption.py video.mp4 --keep-srt

# Fewer words per line (more punchy)
python3 autocaption.py video.mp4 --max-words 3
```

## All Options

| Flag            | Default | Description                                     |
|-----------------|---------|-------------------------------------------------|
| `input`         | required | Path to input video                            |
| `-o / --output` | auto     | Output path (default: `input_captioned.mp4`)   |
| `--model`       | `base`   | Whisper model: tiny/base/small/medium/large    |
| `--font-size`   | `75`     | Caption font size in px                         |
| `--font-color`  | `white`  | Text color (white/yellow/black/red/blue/green) |
| `--outline-color`| `black` | Outline color                                   |
| `--margin-v`    | `120`    | Bottom margin in px                             |
| `--max-words`   | `4`      | Words per caption chunk                         |
| `--keep-srt`    | off      | Save .srt file alongside output                 |

## How to Handle User Requests

When a user says something like "add auto captions to this video" and provides a path:

1. Confirm the file exists (if unsure, ask for the path)
2. Run the script with default settings
3. Report the output path when done

If the user mentions a style preference (big text, yellow, etc.), map it to the appropriate flag and include it in the command.

## Troubleshooting

**`No such filter: subtitles`**
FFmpeg was built without libass. Fix: `brew reinstall ffmpeg` (macOS).

**Captions missing or wrong words**
Use a larger Whisper model: `--model small` or `--model medium`.

**Script hangs on transcription**
Normal for longer videos on CPU — `base` model takes ~1× real-time. Use `--model tiny` for speed.

**Text too small on phone preview**
Increase `--font-size` to 85–100.

## Additional Resources

- **`scripts/autocaption.py`** — The full captioning script
- **`references/caption-styling.md`** — Styling guide, color table, Whisper model comparison, and troubleshooting
