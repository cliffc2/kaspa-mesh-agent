# -------------------------------------------------
# media_utils.py
# Encode/decode tiny PNG/JPEG or 8-kHz mono WAV for LoRa transport
# -------------------------------------------------
import base64, time
from pathlib import Path


def encode_media(file_path: Path) -> tuple[str, str]:
    """Return (b64_string, file_extension) ready for a mesh payload."""
    ext = file_path.suffix.lower().lstrip(".")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return b64, ext


def decode_media(
    b64_str: str, ext: str = "png", out_dir: Path = Path("media_received")
) -> Path:
    """Write the decoded data to disk and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(b64_str)
    out_path = out_dir / f"{int(time.time())}.{ext}"
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path
