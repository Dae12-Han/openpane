"""
openpane.generator
Generate weather background images on demand and cache them.
- macOS / iTerm2 → animated GIF
- Windows Terminal → static PNG (Windows Terminal doesn't animate GIFs)
"""

import os
import math
import random
from pathlib import Path
from typing import Tuple, Callable, List

# Pillow is imported lazily so importing the package without it doesn't crash
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Image dimensions — 1080p works well as a terminal background
WIDTH, HEIGHT = 1920, 1080
FRAMES = 30
FRAME_DURATION_MS = 80


def cache_dir() -> Path:
    """Return (and create if missing) the cache directory for generated assets."""
    d = Path.home() / ".openpane" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Particle generators ─────────────────────────────────────
def _spring_particles():
    random.seed(42)
    return [
        {
            "x": random.uniform(0, WIDTH),
            "y": random.uniform(0, HEIGHT),
            "vx": random.uniform(-1.5, 1.5),
            "vy": random.uniform(1.5, 3.5),
            "size": random.randint(8, 16),
            "color": (255, random.randint(150, 200), random.randint(180, 220)),
        }
        for _ in range(80)
    ]

def _rain_particles():
    random.seed(43)
    return [
        {
            "x": random.uniform(0, WIDTH),
            "y": random.uniform(0, HEIGHT),
            "vy": random.uniform(20, 35),
            "size": random.randint(2, 4),
            "color": (100, 140, 180),
        }
        for _ in range(150)
    ]

def _snow_particles():
    random.seed(44)
    return [
        {
            "x": random.uniform(0, WIDTH),
            "y": random.uniform(0, HEIGHT),
            "vx": random.uniform(-0.8, 0.8),
            "vy": random.uniform(1.0, 2.5),
            "size": random.randint(4, 10),
            "phase": random.uniform(0, 6.28),
            "color": (235, 240, 250),
        }
        for _ in range(100)
    ]

def _clear_particles():
    random.seed(45)
    return [
        {
            "x": random.uniform(0, WIDTH),
            "y": random.uniform(50, HEIGHT // 3),
            "vx": random.uniform(0.3, 0.8),
            "size": random.randint(40, 80),
            "color": (220, 230, 240),
        }
        for _ in range(15)
    ]

def _night_particles():
    random.seed(46)
    return [
        {
            "x": random.uniform(0, WIDTH),
            "y": random.uniform(0, HEIGHT),
            "size": random.randint(1, 4),
            "phase": random.uniform(0, 6.28),
        }
        for _ in range(120)
    ]


# ── Frame steppers ──────────────────────────────────────────
def _step_falling(parts, frame_idx):
    """Generic gravity-style step (spring blossoms, rain, snow)."""
    for p in parts:
        # Optional sway based on a sine phase (snow uses this)
        sway = math.sin(p.get("phase", 0) + frame_idx * 0.2) * 1.5 if "phase" in p else 0
        p["x"] += p.get("vx", 0) + sway
        p["y"] += p["vy"]
        if p["y"] > HEIGHT:
            p["y"] = -20
            p["x"] = random.uniform(0, WIDTH)
        if p["x"] < 0: p["x"] = WIDTH
        if p["x"] > WIDTH: p["x"] = 0
    return parts

def _step_drifting(parts, frame_idx):
    """Cloud-style horizontal drift."""
    for p in parts:
        p["x"] += p["vx"]
        if p["x"] - p["size"] > WIDTH:
            p["x"] = -p["size"]
            p["y"] = random.uniform(50, HEIGHT // 3)
    return parts

def _step_twinkle(parts, frame_idx):
    """Stars that brighten and dim."""
    out = []
    for p in parts:
        twinkle = (math.sin(p["phase"] + frame_idx * 0.3) + 1) / 2
        brightness = int(150 + twinkle * 105)
        p["color"] = (brightness, brightness, min(255, brightness + 20))
        out.append(p)
    return out


# ── Asset definitions ───────────────────────────────────────
ASSETS = {
    "spring": {
        "bg": (255, 200, 220),
        "particles": _spring_particles,
        "step": _step_falling,
    },
    "rain": {
        "bg": (40, 55, 75),
        "particles": _rain_particles,
        "step": _step_falling,
    },
    "snow": {
        "bg": (200, 215, 230),
        "particles": _snow_particles,
        "step": _step_falling,
    },
    "clear": {
        "bg": (135, 180, 220),
        "particles": _clear_particles,
        "step": _step_drifting,
    },
    "night": {
        "bg": (10, 15, 35),
        "particles": _night_particles,
        "step": _step_twinkle,
    },
}


def _draw_frame(parts, bg_color):
    """Render a single frame of particles into a PIL Image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)
    for p in parts:
        s = p["size"]
        x, y = p["x"], p["y"]
        draw.ellipse([x - s, y - s, x + s, y + s], fill=p["color"])
    return img


# ── Public API ──────────────────────────────────────────────
def generate_gif(asset_name: str) -> Path:
    """
    Generate (or reuse cached) animated GIF for the given asset.
    Returns the absolute path to the GIF on disk.
    """
    if not HAS_PIL:
        raise RuntimeError("Pillow is required. Install with: pip install Pillow")

    out = cache_dir() / f"{asset_name}.gif"
    if out.exists():
        return out

    spec = ASSETS[asset_name]
    parts = spec["particles"]()
    step = spec["step"]
    bg = spec["bg"]

    frames = []
    for f in range(FRAMES):
        parts = step(parts, f)
        frames.append(_draw_frame(parts, bg))

    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
    )
    return out


def generate_png(asset_name: str) -> Path:
    """
    Generate (or reuse cached) static PNG for the given asset.
    Used on Windows since Windows Terminal doesn't animate GIFs.
    """
    if not HAS_PIL:
        raise RuntimeError("Pillow is required. Install with: pip install Pillow")

    out = cache_dir() / f"{asset_name}.png"
    if out.exists():
        return out

    spec = ASSETS[asset_name]
    parts = spec["particles"]()
    step = spec["step"]
    bg = spec["bg"]

    # Step the simulation a few times so particles look mid-flow
    for f in range(15):
        parts = step(parts, f)

    img = _draw_frame(parts, bg)
    img.save(out, "PNG", optimize=True)
    return out


def clear_cache():
    """Delete all cached generated images."""
    for f in cache_dir().glob("*"):
        try:
            f.unlink()
        except OSError:
            pass
