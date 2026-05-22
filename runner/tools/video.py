"""
Video assembly tool — combines voiceover audio + background images into a finished MP4.
Output is 9:16 vertical (1080x1920) suitable for TikTok, Instagram Reels, YouTube Shorts.
Uses MoviePy + Pillow. FFmpeg is bundled with MoviePy.
"""
import os
from pathlib import Path
from datetime import datetime

VIDEOS_DIR = Path(__file__).parent.parent.parent / "workspace" / "social" / "ready-to-post"
ASSETS_DIR = Path(__file__).parent.parent.parent / "workspace" / "assets"

# TikTok/Reels vertical format
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920


def _pad_image_to_vertical(img_path: str) -> str:
    """Resize and pad an image to 1080x1920 (9:16). Returns path to processed image."""
    from PIL import Image, ImageFilter
    import tempfile

    img = Image.open(img_path).convert("RGB")
    target_w, target_h = VIDEO_WIDTH, VIDEO_HEIGHT

    # Scale to fill height, then crop width (or scale to fill width, crop height)
    img_ratio    = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        # Image is wider — scale by height
        new_h = target_h
        new_w = int(img.width * (target_h / img.height))
    else:
        # Image is taller — scale by width
        new_w = target_w
        new_h = int(img.height * (target_w / img.width))

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Create blurred background (same image, scaled to fill, blurred)
    bg = img.resize((target_w, target_h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(radius=20))

    # Paste resized image centered over blurred background
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    bg.paste(img_resized, (x_off, y_off))

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    bg.save(tmp.name, "JPEG", quality=92)
    return tmp.name


def assemble_video(
    audio_file: str,
    image_files: list[str],
    title: str,
    output_name: str = "",
) -> dict:
    """
    Combine voiceover audio + background images into a finished vertical MP4.

    Args:
        audio_file:   Path to the voiceover MP3 (from audio_generation tool)
        image_files:  List of image paths (from image_generation tool) — 3-6 images
        title:        Video title (used for filename)
        output_name:  Optional override for output filename

    Returns:
        dict with success, video_path, duration_seconds
    """
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    except ImportError:
        return {"error": "moviepy not installed — run: pip install moviepy"}

    audio_path = Path(audio_file)
    if not audio_path.exists():
        return {"error": f"Audio file not found: {audio_file}"}

    valid_images = [p for p in image_files if Path(p).exists()]
    if not valid_images:
        return {"error": "No valid image files found"}

    try:
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

        # Load audio to get total duration
        audio_clip = AudioFileClip(str(audio_path))
        total_duration = audio_clip.duration

        # Split duration evenly across images
        per_image = total_duration / len(valid_images)

        # Build one ImageClip per image
        processed = [_pad_image_to_vertical(p) for p in valid_images]
        clips = [
            ImageClip(p).with_duration(per_image)
            for p in processed
        ]

        # Concatenate image clips, attach audio
        video = concatenate_videoclips(clips, method="compose")
        video = video.with_audio(audio_clip)

        # Output filename
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = (output_name or title).lower().replace(" ", "-")[:40]
        out_path = VIDEOS_DIR / f"{ts}-{slug}.mp4"

        video.write_videofile(
            str(out_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None,   # suppress verbose MoviePy output
        )

        # Clean up temp files
        for p in processed:
            try:
                Path(p).unlink()
            except Exception:
                pass

        audio_clip.close()
        video.close()

        return {
            "success":          True,
            "video_path":       str(out_path),
            "duration_seconds": round(total_duration, 1),
            "images_used":      len(valid_images),
            "message":          f"Video ready: {out_path.name} — upload to TikTok/Reels",
        }

    except Exception as exc:
        return {"error": str(exc)}


TOOL_SPEC = {
    "name": "assemble_video",
    "description": (
        "Combine a voiceover audio file and background images into a finished vertical MP4 "
        "(1080x1920, 9:16) ready to upload to TikTok, Instagram Reels, Facebook Reels, or YouTube Shorts. "
        "Call this AFTER audio_generation and image_generation have produced their files."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "audio_file": {
                "type": "string",
                "description": "Full path to the voiceover MP3 file produced by audio_generation",
            },
            "image_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of full paths to background images produced by image_generation (3-6 images)",
            },
            "title": {
                "type": "string",
                "description": "Short title used for the output filename",
            },
            "output_name": {
                "type": "string",
                "description": "Optional custom output filename (no extension)",
                "default": "",
            },
        },
        "required": ["audio_file", "image_files", "title"],
    },
}
