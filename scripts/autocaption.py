#!/usr/bin/env python3
"""
autocaption.py — Add burned-in auto-captions to a local UGC video using Whisper + FFmpeg.

Usage:
    python3 autocaption.py input_video.mp4
    python3 autocaption.py input_video.mp4 -o captioned_output.mp4
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
DEFAULT_FONT_SIZE = 45         # medium size, readable without being too large
DEFAULT_FONT_COLOR = "white"   # CSS color name
DEFAULT_OUTLINE_COLOR = "black"
DEFAULT_OUTLINE = 2
DEFAULT_SHADOW = 1
DEFAULT_MARGIN_V = 80          # near bottom but not clipped (px)
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
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        errors.append("  Pillow not found — pip install Pillow")
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


def parse_srt(srt_path: Path) -> list[tuple[float, float, str]]:
    """Parse SRT file into list of (start_sec, end_sec, text) tuples."""
    def ts_to_sec(ts: str) -> float:
        h, m, rest = ts.strip().split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    entries = []
    content = srt_path.read_text(encoding="utf-8")
    for block in content.strip().split("\n\n"):
        lines = block.strip().splitlines()
        for i, line in enumerate(lines):
            if "-->" in line:
                try:
                    start_str, end_str = line.split("-->")
                    start = ts_to_sec(start_str)
                    end = ts_to_sec(end_str)
                    text = " ".join(lines[i + 1:]).strip()
                    if text:
                        entries.append((start, end, text))
                except Exception:
                    pass
                break
    return entries


def get_video_info(video_path: Path) -> dict:
    """Return width, height, fps_num, fps_den, fps, duration via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json",
            str(video_path),
        ],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    fps_num, fps_den = map(int, stream["r_frame_rate"].split("/"))
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps_num": fps_num,
        "fps_den": fps_den,
        "fps": fps_num / fps_den,
        "duration": float(data["format"]["duration"]),
    }


def find_font(font_size: int):
    """Return a PIL ImageFont. Tries bold system fonts, falls back to default."""
    from PIL import ImageFont
    candidates = [
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, font_size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def make_caption_image(
    text: str, width: int, height: int,
    font_size: int, font_color: str, outline_color: str,
    outline_size: int, margin_v: int,
):
    """Return a transparent RGBA PIL Image with the caption text burned in."""
    from PIL import Image, ImageDraw

    color_map = {
        "white":  (255, 255, 255, 255),
        "black":  (0,   0,   0,   255),
        "yellow": (255, 255, 0,   255),
        "red":    (255, 0,   0,   255),
        "blue":   (0,   0,   255, 255),
        "green":  (0,   255, 0,   255),
    }
    fc = color_map.get(font_color.lower(),   (255, 255, 255, 255))
    oc = color_map.get(outline_color.lower(), (0,   0,   0,   255))

    font = find_font(font_size)
    img  = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x = width // 2
    y = height - margin_v

    # Outline: draw text at each neighbouring offset
    for ox in range(-outline_size, outline_size + 1):
        for oy in range(-outline_size, outline_size + 1):
            if ox != 0 or oy != 0:
                draw.text((x + ox, y + oy), text, font=font, fill=oc, anchor="ms")
    # Main text
    draw.text((x, y), text, font=font, fill=fc, anchor="ms")

    return img


def burn_captions(
    video_path: Path, srt_path: Path, output_path: Path,
    font_size: int, font_color: str, outline_color: str,
    outline_size: int, margin_v: int,
) -> None:
    """Burn captions via Pillow RGBA overlay piped into FFmpeg's overlay filter."""
    print("[3/3] Burning captions with Pillow + FFmpeg overlay…")

    info = get_video_info(video_path)
    width, height    = info["width"], info["height"]
    fps_num, fps_den = info["fps_num"], info["fps_den"]
    duration         = info["duration"]

    captions = parse_srt(srt_path)

    # Pre-render each unique caption text once
    caption_cache: dict[str, bytes] = {}
    for (_, _, text) in captions:
        if text not in caption_cache:
            img = make_caption_image(
                text, width, height,
                font_size, font_color, outline_color, outline_size, margin_v,
            )
            caption_cache[text] = img.tobytes()

    blank_frame = bytes(width * height * 4)   # fully transparent RGBA
    fps_str     = f"{fps_num}/{fps_den}"
    total_frames = int(duration * fps_num / fps_den) + 2

    ffmpeg_proc = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            # Pipe: RGBA caption overlay
            "-f", "rawvideo", "-pix_fmt", "rgba",
            "-s", f"{width}x{height}",
            "-r", fps_str,
            "-i", "pipe:0",
            # Composite overlay onto source
            "-filter_complex", "[0:v][1:v]overlay=format=auto",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for frame_num in range(total_frames):
        timestamp  = frame_num * fps_den / fps_num
        frame_data = blank_frame
        for (start, end, text) in captions:
            if start <= timestamp < end:
                frame_data = caption_cache[text]
                break
        try:
            ffmpeg_proc.stdin.write(frame_data)
        except BrokenPipeError:
            break

    ffmpeg_proc.stdin.close()
    stderr = ffmpeg_proc.stderr.read()
    ffmpeg_proc.wait()

    if ffmpeg_proc.returncode != 0:
        print("FFmpeg error:\n", stderr.decode()[-2000:])
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

    # Burn captions
    burn_captions(
        video_path, srt_tmp, output_path,
        font_size=args.font_size,
        font_color=args.font_color,
        outline_color=args.outline_color,
        outline_size=DEFAULT_OUTLINE,
        margin_v=args.margin_v,
    )

    srt_tmp.unlink(missing_ok=True)

    print(f"\nDone! Output saved to:\n  {output_path}")


if __name__ == "__main__":
    main()
