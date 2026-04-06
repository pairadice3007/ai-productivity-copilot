import base64
import ctypes
import io
from PIL import Image
import mss

# Tell Windows we are DPI-aware so mss captures at logical resolution
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

_mss = mss.mss()
_last_img: Image.Image | None = None


def capture_primary() -> Image.Image:
    monitor = _mss.monitors[1]  # primary monitor only
    raw = _mss.grab(monitor)
    return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def compute_diff(img_a: Image.Image, img_b: Image.Image) -> float:
    """Return fraction of pixels that differ (0.0–1.0). Fast 100×60 downsample."""
    thumb_size = (100, 60)
    a = img_a.resize(thumb_size).convert("L")
    b = img_b.resize(thumb_size).convert("L")
    pixels_a = list(a.getdata())
    pixels_b = list(b.getdata())
    total = len(pixels_a)
    changed = sum(1 for x, y in zip(pixels_a, pixels_b) if abs(x - y) > 10)
    return changed / total


def resize_for_api(img: Image.Image, max_px: int = 1568) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_px:
        return img
    ratio = max_px / max(w, h)
    return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)


def to_base64_jpeg(img: Image.Image, quality: int = 85) -> str:
    img = resize_for_api(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    del img, buf
    return data


def get_screenshot_b64() -> tuple[str, Image.Image]:
    """
    Capture, compare with last screenshot, return (base64_jpeg, raw_img).
    Caller should store raw_img as the new _last for diffing next cycle.
    """
    global _last_img
    new_img = capture_primary()
    diff = compute_diff(_last_img, new_img) if _last_img is not None else 1.0
    _last_img = new_img.copy()
    b64 = to_base64_jpeg(new_img)
    del new_img
    return b64, diff
