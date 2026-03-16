# Caption Styling Reference

## Default UGC Style

The skill ships with big, bold captions tuned for UGC / short-form content:

| Parameter   | Default | Notes                                      |
|-------------|---------|---------------------------------------------|
| FontSize    | 75      | Large — readable on phone screens           |
| Bold        | 1       | Always on                                   |
| FontColor   | white   | Best contrast on most footage               |
| OutlineColor| black   | Keeps text legible on bright backgrounds    |
| Outline     | 3px     | Thick enough to pop                         |
| Shadow      | 1       | Subtle depth                                |
| Alignment   | 2       | Bottom-center (standard TikTok/Reels style) |
| MarginV     | 120px   | Keeps text away from the very bottom edge   |
| MaxWords    | 4       | Short bursts — easy to read while scrolling |

## Tweaking via CLI Flags

```bash
# Bigger text
python3 autocaption.py video.mp4 --font-size 90

# Yellow text (popular on dark footage)
python3 autocaption.py video.mp4 --font-color yellow

# Higher margin (avoid covering lower-third graphics)
python3 autocaption.py video.mp4 --margin-v 200

# Fewer words per line (more punchy)
python3 autocaption.py video.mp4 --max-words 3

# Keep the SRT file (useful for editing in CapCut / Premiere)
python3 autocaption.py video.mp4 --keep-srt
```

## ASS Color Format

FFmpeg's `force_style` uses ASS color: `&HAABBGGRR` (alpha, blue, green, red — little-endian).

| Color  | ASS Value   |
|--------|-------------|
| White  | &H00FFFFFF  |
| Black  | &H00000000  |
| Yellow | &H0000FFFF  |
| Red    | &H000000FF  |
| Blue   | &H00FF0000  |
| Green  | &H0000FF00  |

## Whisper Model Sizes

| Model  | Speed    | Accuracy | Best For                    |
|--------|----------|----------|-----------------------------|
| tiny   | fastest  | low      | quick drafts                |
| base   | fast     | decent   | **default — good balance**  |
| small  | moderate | good     | accented speech             |
| medium | slow     | great    | complex vocabulary          |
| large  | slowest  | best     | multiple speakers, noisy bg |

Upgrade model: `--model small` or `--model medium`.

## FFmpeg subtitles Filter Notes

- The `subtitles` filter requires `libass` in your FFmpeg build.
  - macOS: `brew install ffmpeg` includes libass by default.
  - Ubuntu: `sudo apt install ffmpeg` also includes it.
- If you get `No such filter: subtitles`, reinstall FFmpeg with libass support.
- SRT path must be an **absolute path** or relative path with no special characters.
  Use the temp file approach in the script to avoid path issues.

## Troubleshooting

**No captions in output**
- Check if Whisper produced any output — run with `--model small` for better accuracy on quiet audio.

**Captions cut off at edges**
- Reduce `--font-size` or increase `--margin-v`.

**Text too small on phone**
- Increase `--font-size` (try 85–100 for very large text).

**Script runs but Whisper hangs**
- Large model on CPU is slow. Switch to `--model base` or `--model tiny` for speed.
- If you have an Apple Silicon Mac: `pip install openai-whisper` uses MPS acceleration automatically.
