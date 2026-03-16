#!/usr/bin/env python3
"""
autocaption.py — Add burned-in auto-captions to a local UGC video using Whisper + FFmpeg.

Usage:
    python3 autocaption.py input_video.mp4
    python3 autocaption.py input_video.mp4 -o captioned_output.mp4
    python3 autocaption.py input_video.mp4 --style word   # word-by-word highlight
    python3 autocaption.py input_video.mp4 --font-size 80

Requires:
    pip install openai-whisper
    brew install ffmpeg   # macOS
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


# ── Caption style defaults (UGC-optimised: big, bold, readable) ──────────────
DEFAULT_FONT_SIZE = 75         # large and readable on mobile
DEFAULT_FONT_COLOR = "white"   # &H00FFFFFF in ASS hex
DEFAULT_OUTLINE_COLOR = "black"
DEFAULT_OUTLINE = 3
DEFAULT_SHADOW = 1
DEFAULT_MARGIN_V = 120         # distance from bottom edge (px)
DEFAULT_MAX_WORDS = 4          # max words per caption line


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_deps():
    errors = []
    for tool in ("ffmpeg", "ffprobe"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            errors.append(f"  {tool} not found — brew install ffmpeg")
    try:
        import whisper  # noqa: F401
    except ImportError:
        errors.append("  openai-whisper not found — pip install openai-whisper")
    if errors:
        print("Missing dependencies:\n" + "\n".join(errors))
        sys.exit(1)


def transcribe(video_path: Path, model_name: str = "base") -> list[dict]:
    """Run Whisper on the video and return word-level segments."""
    import whisper

    print(f"[1/3] Transcribing with Whisper ({model_name})…")
    model = whisper.load_model(model_name)
    result = model.transcribe(str(video_path), word_timestamps=True, verbose=False)
    return result["segments"]


def segments_to_srt(segments: list[dict], max_words: int) -> str:
    """Convert Whisper segments into an SRT string, chunked by max_words."""

    def fmt_ts(secs: float) -> str:
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        ms = int(round((secs - int(secs)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    idx = 1
    for seg in segments:
        words = seg.get("words", [])
        if not words:
            # Fall back to segment-level entry
            lines.append(f"{idx}")
            lines.append(f"{fmt_ts(seg['start'])} --> {fmt_ts(seg['end'])}")
            lines.append(seg["text"].strip())
            lines.append("")
            idx += 1
            continue

        # Chunk words into groups of max_words
        for i in range(0, len(words), max_words):
            chunk = words[i : i + max_words]
            start = chunk[0]["start"]
            end = chunk[-1]["end"]
            text = " ".join(w["word"].strip() for w in chunk)
            lines.append(f"{idx}")
            lines.append(f"{fmt_ts(start)} --> {fmt_ts(end)}")
            lines.append(text)
            lines.append("")
            idx += 1

    return "\n".join(lines)


def build_ffmpeg_style(font_size: int, font_color: str, outline_color: str,
                       outline: int, shadow: int, margin_v: int) -> str:
    """Build the FFmpeg subtitles filter force_style string."""

    def color_to_ass(c: str) -> str:
        """Convert a CSS-like color name/hex to ASS &HAABBGGRR format."""
        table = {
            "white":  "&H00FFFFFF",
            "black":  "&H00000000",
            "yellow": "&H0000FFFF",
            "red":    "&H000000FF",
            "blue":   "&H00FF0000",
            "green":  "&H0000FF00",
        }
        return table.get(c.lower(), "&H00FFFFFF")

    return (
        f"FontSize={font_size},"
        "Bold=1,"
        f"PrimaryColour={color_to_ass(font_color)},"
        f"OutlineColour={color_to_ass(outline_color)},"
        f"Outline={outline},"
        f"Shadow={shadow},"
        "Alignment=2,"          # bottom-center
        f"MarginV={margin_v}"
    )


def burn_captions(video_path: Path, srt_path: Path, output_path: Path,
                  style: str) -> None:
    print("[3/3] Burning captions with FFmpeg…")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", "subtitles={}:force_style={}".format(srt_path, style.replace(",", "\\,")),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFmpeg error:\n", result.stderr[-2000:])
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Add auto-captions to a UGC video using Whisper + FFmpeg."
    )
    parser.add_argument("input", help="Path to input video file")
    parser.add_argument("-o", "--output", help="Output file path (default: input_captioned.mp4)")
    parser.add_argument("--model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model (larger = more accurate, slower)")
    parser.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE,
                        help=f"Caption font size (default {DEFAULT_FONT_SIZE})")
    parser.add_argument("--font-color", default=DEFAULT_FONT_COLOR,
                        help="Caption text color (white/yellow/black, default white)")
    parser.add_argument("--outline-color", default=DEFAULT_OUTLINE_COLOR,
                        help="Outline color (default black)")
    parser.add_argument("--margin-v", type=int, default=DEFAULT_MARGIN_V,
                        help=f"Vertical margin from bottom in px (default {DEFAULT_MARGIN_V})")
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS,
                        help=f"Max words per caption chunk (default {DEFAULT_MAX_WORDS})")
    parser.add_argument("--keep-srt", action="store_true",
                        help="Save the generated .srt file alongside the output")
    args = parser.parse_args()

    check_deps()

    video_path = Path(args.input).resolve()
    if not video_path.exists():
        print(f"Error: file not found: {video_path}")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = video_path.with_name(video_path.stem + "_captioned" + video_path.suffix)

    # Transcribe
    segments = transcribe(video_path, model_name=args.model)

    # Build SRT
    print("[2/3] Building SRT captions…")
    srt_content = segments_to_srt(segments, max_words=args.max_words)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
        srt_tmp = Path(f.name)
        f.write(srt_content)

    if args.keep_srt:
        srt_out = output_path.with_suffix(".srt")
        srt_out.write_text(srt_content)
        print(f"    SRT saved: {srt_out}")

    # Build style string
    style = build_ffmpeg_style(
        font_size=args.font_size,
        font_color=args.font_color,
        outline_color=args.outline_color,
        outline=DEFAULT_OUTLINE,
        shadow=DEFAULT_SHADOW,
        margin_v=args.margin_v,
    )

    # Burn captions
    burn_captions(video_path, srt_tmp, output_path, style)

    srt_tmp.unlink(missing_ok=True)

    print(f"\nDone! Output saved to:\n  {output_path}")


if __name__ == "__main__":
    main()
