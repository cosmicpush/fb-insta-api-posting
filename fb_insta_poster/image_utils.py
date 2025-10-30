from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError


class ImageProcessingError(RuntimeError):
    """Raised when local image manipulation fails."""


def convert_png_to_jpeg(png_bytes: bytes) -> bytes:
    """Convert PNG image data to high-quality JPEG bytes."""
    try:
        with Image.open(BytesIO(png_bytes)) as image:
            if image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            ):
                # Blend transparency onto a white background for JPEG output.
                alpha_image = image.convert("RGBA")
                background = Image.new("RGB", alpha_image.size, (255, 255, 255))
                background.paste(alpha_image, mask=alpha_image.split()[-1])
                output_image = background
            else:
                output_image = image.convert("RGB")

            buffer = BytesIO()
            output_image.save(buffer, format="JPEG", quality=95, optimize=True)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageProcessingError(f"Failed to convert image to JPEG: {exc}") from exc


def derive_jpeg_key(original_key: str, jpeg_prefix: Optional[str]) -> str:
    """Create a deterministic JPEG key for the converted image."""
    stem = Path(original_key).stem
    filename = f"{stem}.jpg"
    if jpeg_prefix:
        return f"{jpeg_prefix}/{filename}"
    return filename
