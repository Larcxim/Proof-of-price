"""Shared render kit for the Proof of Price demo video.

Specs (matching the v10 delivery constraints):
    1280x720, 24 fps, H.264 (yuv420p) + AAC, no voiceover.
Palette deliberately avoids teal/blue accents (amber + warm neutrals + green/red
for direction only), so nothing reads as a stock fintech template.

Every on-screen string that describes data is expected to carry a provenance
label ("SAVED" / "OBSERVED" / "NOT QUOTE TIME" / "EDITORIAL CAPTION"), because
the project's guardrail is that missing fields stay visibly missing and that
nothing is presented as an executable trade or an independent equity tape.
"""

from __future__ import annotations

import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- constants

W, H = 1280, 720
FPS = 24

BG_TOP = (11, 11, 13)
BG_BOT = (17, 16, 15)
INK = (238, 236, 232)
INK_DIM = (154, 152, 148)
INK_FAINT = (96, 94, 91)
AMBER = (245, 165, 36)
AMBER_DIM = (176, 118, 28)
GREEN = (74, 190, 108)
RED = (229, 83, 75)
RULE = (44, 42, 40)
PLATE = (22, 21, 20)

_FONT_DIRS = [
    "/usr/lib/R/library/grDevices/fonts/Montserrat/static",
    "/usr/lib/R/library/grDevices/fonts/Roboto",
    "/usr/share/fonts/truetype/dejavu",
]

_FACES = {
    "display": ("Montserrat-BoldItalic.ttf", "Montserrat-BoldItalic"),
    "body": ("Roboto-Medium.ttf", "Roboto-Medium"),
    "mono": ("DejaVuSansMono.ttf", "DejaVuSansMono"),
    "sans": ("DejaVuSans.ttf", "DejaVuSans"),
    "sansbold": ("DejaVuSans-Bold.ttf", "DejaVuSans-Bold"),
}
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _find(name: str) -> str:
    for d in _FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def font(face: str, size: int) -> ImageFont.FreeTypeFont:
    key = (face, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(_find(_FACES[face][0]), size)
    return _font_cache[key]


# ---------------------------------------------------------------- easing


def ease_out_cubic(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ramp(t: float, start: float, dur: float) -> float:
    """0 before start, 1 after start+dur."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return min(max((t - start) / dur, 0.0), 1.0)


def fade(t: float, start: float, dur: float, fin: float = 0.25, fout: float = 0.25) -> float:
    """Opacity envelope for a cue lasting `dur` from `start`."""
    if t < start or t > start + dur:
        return 0.0
    a = ramp(t, start, fin)
    b = 1 - ramp(t, start + dur - fout, fout)
    return min(a, b)


# ---------------------------------------------------------------- primitives


def base_frame(t: float) -> Image.Image:
    """Near-black warm gradient + faint grid + slow vignette drift."""
    g = np.linspace(0.0, 1.0, H)[:, None, None]  # (H,1,1) -> broadcasts across W and channels
    top = np.array(BG_TOP, dtype=np.float32)[None, None, :]
    bot = np.array(BG_BOT, dtype=np.float32)[None, None, :]
    arr = top + g * (bot - top)                                   # (H,1,3)
    img = Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8))  # (H,W,3)
    d = ImageDraw.Draw(img, "RGBA")

    # faint grid, drifting very slowly (designed motion, not captured footage)
    off = (t * 6.0) % 64
    for x in range(-64, W + 64, 64):
        d.line([(x + off, 0), (x + off, H)], fill=(255, 255, 255, 5), width=1)
    for y in range(0, H, 64):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 4), width=1)

    # vignette
    vig = Image.new("L", (W // 4, H // 4), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-W // 8, -H // 8, W // 4 + W // 8, H // 4 + H // 8], fill=255)
    vig = vig.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(80))
    shade = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(img, shade, vig.point(lambda p: int(p * 0.92 + 20)))
    return img.convert("RGBA")  # RGBA so every cue can carry a real alpha fade


def text(
    img: Image.Image,
    xy: tuple[int, int],
    s: str,
    face: str = "body",
    size: int = 26,
    fill=INK,
    anchor: str = "la",
    alpha: float = 1.0,
    tracking: int = 0,
):
    if alpha <= 0.003:
        return
    d = ImageDraw.Draw(img, "RGBA")
    f = font(face, size)
    col = (fill[0], fill[1], fill[2], int(255 * min(max(alpha, 0), 1)))
    if tracking:
        # manual letter-spacing: draw glyph by glyph
        x, y = xy
        if "m" in anchor:
            total = sum(d.textlength(c, font=f) + tracking for c in s) - tracking
            x -= total / 2 if "a" not in anchor else total
        for c in s:
            d.text((x, y), c, font=f, fill=col, anchor=anchor)
            x += d.textlength(c, font=f) + tracking
        return
    d.text(xy, s, font=f, fill=col, anchor=anchor)


def plate(
    img: Image.Image,
    box: tuple[int, int, int, int],
    alpha: float = 1.0,
    fill=PLATE,
    edge: tuple[int, int, int] | None = RULE,
    radius: int = 6,
):
    if alpha <= 0.003:
        return
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(box, radius=radius, fill=(*fill, int(235 * alpha)))
    if edge:
        od.rounded_rectangle(box, radius=radius, outline=(*edge, int(255 * alpha)), width=1)
    img.alpha_composite(overlay) if img.mode == "RGBA" else img.paste(
        Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0)
    )


def tag(
    img: Image.Image,
    xy: tuple[int, int],
    label: str,
    alpha: float = 1.0,
    colour=AMBER,
    face: str = "mono",
    size: int = 19,
):
    """Small provenance / status tag: a bordered pill with mono type."""
    if alpha <= 0.003:
        return
    f = font(face, size)
    d = ImageDraw.Draw(img)
    tw = int(d.textlength(label, font=f))
    pad_x, pad_y = 12, 7
    x, y = xy
    plate(img, (x, y, x + tw + 2 * pad_x, y + size + 2 * pad_y), alpha=alpha, fill=(20, 19, 18))
    dd = ImageDraw.Draw(img, "RGBA")
    dd.rounded_rectangle(
        (x, y, x + tw + 2 * pad_x, y + size + 2 * pad_y),
        radius=6,
        outline=(*colour, int(150 * alpha)),
        width=1,
    )
    text(img, (x + pad_x, y + pad_y - 2), label, face=face, size=size, fill=colour, alpha=alpha)
    return tw + 2 * pad_x


def hrule(img: Image.Image, y: int, x0: int, x1: int, alpha: float = 1.0, colour=RULE, w: int = 1):
    d = ImageDraw.Draw(img, "RGBA")
    d.line([(x0, y), (x1, y)], fill=(*colour, int(255 * alpha)), width=w)


def basis_bar(
    img: Image.Image,
    cx: int,
    y: int,
    half: int,
    value_bp: float,
    scale_bp: float,
    alpha: float,
    colour=AMBER,
    ticks: bool = True,
):
    """Zero-centred basis bar. Zero stays at centre; nothing is drawn as a price axis."""
    if alpha <= 0.003:
        return
    d = ImageDraw.Draw(img, "RGBA")
    a = int(255 * alpha)
    d.line([(cx - half, y), (cx + half, y)], fill=(60, 58, 55, a), width=3)
    for k in (-1, 1):
        d.line([(cx + k * half, y - 7), (cx + k * half, y + 7)], fill=(72, 70, 66, a), width=2)
    d.line([(cx, y - 11), (cx, y + 11)], fill=(120, 116, 110, a), width=2)
    frac = max(-1.0, min(1.0, value_bp / scale_bp))
    ex = cx + int(frac * half)
    d.line([(cx, y), (ex, y)], fill=(*colour, a), width=6)
    d.ellipse([(ex - 7, y - 7), (ex + 7, y + 7)], fill=(*colour, a))
    if ticks:
        text(img, (cx - half, y + 20), f"-{scale_bp:g} bp", "mono", 17, INK_FAINT, alpha=alpha)
        text(img, (cx + half, y + 20), f"+{scale_bp:g} bp", "mono", 17, INK_FAINT, "ra", alpha=alpha)
        text(img, (cx, y + 20), "0", "mono", 17, INK_FAINT, "ma", alpha=alpha)


# ---------------------------------------------------------------- audio


def ambient_bed(seconds: float, peak_dbfs: float = -2.72, sr: int = 48000) -> np.ndarray:
    """Sparse, non-melodic ambient bed: low pad + slow noise swell.

    Peak-normalised to `peak_dbfs` so the delivery matches the documented
    headroom (no voiceover, no music claims, no clipping).
    """
    n = int(seconds * sr)
    t = np.arange(n) / sr
    pad = (
        0.55 * np.sin(2 * math.pi * 55.0 * t)
        + 0.34 * np.sin(2 * math.pi * 82.5 * t + 0.4)
        + 0.20 * np.sin(2 * math.pi * 110.0 * t + 0.9)
        + 0.10 * np.sin(2 * math.pi * 164.8 * t + 1.7)
    )
    lfo = 0.55 + 0.45 * np.sin(2 * math.pi * (0.045) * t)
    pad = pad * lfo
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n).astype(np.float32)
    # gaussian smoothing for a breathy texture (vectorised: fast enough for 125 s)
    from scipy.ndimage import gaussian_filter1d

    sm = gaussian_filter1d(noise, sigma=int(sr * 0.03))
    sm = sm / (np.max(np.abs(sm)) + 1e-9)
    swell = 0.5 + 0.5 * np.sin(2 * math.pi * (0.021) * t + 1.1)
    bed = 0.72 * pad + 0.55 * sm * swell
    fade_n = min(int(0.9 * sr), n // 4)
    env = np.ones(n)
    env[:fade_n] = np.linspace(0, 1, fade_n)
    env[-fade_n:] = np.linspace(1, 0, fade_n)
    bed = bed * env
    bed = bed / (np.max(np.abs(bed)) + 1e-9)
    return (bed * (10 ** (peak_dbfs / 20.0))).astype(np.float32)


# ---------------------------------------------------------------- sound design


def _exp(n: int, tau: float, sr: int) -> np.ndarray:
    t = np.arange(n) / sr
    return np.exp(-t / tau)


def synth_event(kind: str, sr: int = 48000, dur: float | None = None, rng=None):
    """Short synthesised UI/foley events. All procedural: no licensed audio."""
    if rng is None:
        rng = np.random.default_rng(11)
    if kind == "tick":          # soft material tick on beat changes
        d = 0.06; n = int(d * sr); t = np.arange(n) / sr
        hp = np.diff(rng.standard_normal(n).astype(np.float32), prepend=0.0)
        s = 0.5 * hp * _exp(n, 0.006, sr) + 0.5 * np.sin(2 * np.pi * 1900 * t) * _exp(n, 0.012, sr)
    elif kind == "click":       # UI click for cursor actions
        d = 0.045; n = int(d * sr); t = np.arange(n) / sr
        hp = np.diff(rng.standard_normal(n).astype(np.float32), prepend=0.0)
        s = 0.6 * hp * _exp(n, 0.0035, sr) + 0.4 * np.sin(2 * np.pi * 1250 * t) * _exp(n, 0.009, sr)
    elif kind == "thud":        # low transition thud
        d = 0.22; n = int(d * sr); t = np.arange(n) / sr
        s = np.sin(2 * np.pi * 72 * t) * _exp(n, 0.05, sr) + 0.6 * np.sin(2 * np.pi * 48 * t) * _exp(n, 0.08, sr)
    elif kind == "chime":       # closing lockup chime
        d = 1.8; n = int(d * sr); t = np.arange(n) / sr
        s = (np.sin(2 * np.pi * 440 * t) + 0.6 * np.sin(2 * np.pi * 660 * t)
             + 0.3 * np.sin(2 * np.pi * 880 * t)) * _exp(n, 0.55, sr)
    elif kind == "whoosh":      # scroll air under the dashboard walk
        d = dur or 1.0; n = int(d * sr); t = np.arange(n) / sr
        from scipy.ndimage import gaussian_filter1d
        noise = rng.standard_normal(n).astype(np.float32)
        sm = gaussian_filter1d(noise, sigma=int(sr * 0.04))
        sm = sm / (np.max(np.abs(sm)) + 1e-9)
        s = sm * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    else:
        raise ValueError(kind)
    return s.astype(np.float32)


LEVELS = {"tick": 0.16, "click": 0.20, "thud": 0.13, "chime": 0.20, "whoosh": 0.10}


def event_mix(seconds: float, events, peak_dbfs: float = -2.72, sr: int = 48000) -> np.ndarray:
    """Ambient bed + timed foley events, normalised so the mix peaks at peak_dbfs."""
    n = int(seconds * sr)
    mix = ambient_bed(seconds, peak_dbfs=0.0, sr=sr) * 0.55
    rng = np.random.default_rng(11)
    for t0, kind, dur in events:
        s = synth_event(kind, sr=sr, dur=dur, rng=rng) * LEVELS[kind]
        i0 = int(t0 * sr)
        if i0 >= n:
            continue
        i1 = min(n, i0 + len(s))
        mix[i0:i1] += s[: i1 - i0]
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * (10 ** (peak_dbfs / 20.0))
    return mix.astype(np.float32)


def write_wav(path: str, samples: np.ndarray, sr: int = 48000):
    pcm = np.clip(samples, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())


# ---------------------------------------------------------------- encode


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(frames, out_path: str, wav_path: str | None, crf: int = 18):
    """Pipe PIL frames straight into libx264, then mux AAC."""
    ff = ffmpeg_exe()
    tmp_v = out_path.replace(".mp4", "_video_only.mp4")
    cmd = [
        ff, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-an", "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "medium", "-crf", str(crf),
        "-movflags", "+faststart", tmp_v,
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for fr in frames:
        p.stdin.write(np.asarray(fr.convert("RGB")).tobytes())
    p.stdin.close()
    p.wait()
    if wav_path:
        cmd2 = [
            ff, "-y", "-i", tmp_v, "-i", wav_path,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart", out_path,
        ]
    else:
        cmd2 = [ff, "-y", "-i", tmp_v, "-c:v", "copy", "-movflags", "+faststart", out_path]
    subprocess.run(cmd2, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(tmp_v)
    return out_path


def probe(path: str) -> dict:
    import json

    ff = ffmpeg_exe().replace("ffmpeg-linux", "ffprobe-linux")
    if not os.path.exists(ff):
        # static imageio build ships ffmpeg only; derive facts from the file header instead
        return {"file": path, "bytes": os.path.getsize(path)}
    out = subprocess.run(
        [ff, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, text=True,
    )
    return json.loads(out.stdout)
