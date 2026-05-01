"""
openpane core
Handles location detection, weather fetching, and terminal rendering.
"""

import sys
import time
import random
import shutil
import threading
import urllib.request
import urllib.error
import json
from dataclasses import dataclass
from typing import Optional


# ── ANSI helpers ───────────────────────────────────────────
def ansi(code: str) -> str:
    return f"\033[{code}"

def bg(r: int, g: int, b: int) -> str:
    """Set terminal background color via RGB."""
    return ansi(f"48;2;{r};{g};{b}m")

def fg(r: int, g: int, b: int) -> str:
    """Set terminal foreground color via RGB."""
    return ansi(f"38;2;{r};{g};{b}m")

RESET   = ansi("0m")
HIDE    = ansi("?25l")   # hide cursor
SHOW    = ansi("?25h")   # show cursor

def move(row: int, col: int) -> str:
    """Move cursor to (row, col)."""
    return ansi(f"{row};{col}H")


# ── WMO weather code → state ────────────────────────────────
def wmo_to_state(code: int) -> str:
    """Convert Open-Meteo WMO weather code to a simple state string."""
    if code == 0:
        return "clear"
    elif code in (1, 2, 3):
        return "cloudy"
    elif code in range(51, 68):
        return "rain"
    elif code in range(71, 78):
        return "snow"
    elif code in range(80, 83):
        return "rain"
    elif code in range(95, 100):
        return "thunder"
    return "clear"


# ── Season detection ────────────────────────────────────────
def get_season(month: int, lat: float) -> str:
    """
    Determine season from month and latitude.
    Southern hemisphere seasons are flipped.
    """
    if lat < 0:
        month = (month + 6 - 1) % 12 + 1
    if month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    elif month in (9, 10, 11):
        return "autumn"
    return "winter"


# ── Sky color palette ───────────────────────────────────────
# Key: (weather_state, time_of_day)
# Value: (bg_r, bg_g, bg_b, fg_r, fg_g, fg_b)
SKY_COLORS = {
    ("clear",   "dawn"):   (255, 160,  80, 255, 200, 120),
    ("clear",   "day"):    ( 30, 100, 180,  80, 160, 230),
    ("clear",   "dusk"):   (180,  80,  40, 220, 130,  60),
    ("clear",   "night"):  (  8,  12,  35,  60,  80, 140),
    ("cloudy",  "dawn"):   (160, 130, 110, 200, 170, 140),
    ("cloudy",  "day"):    ( 80,  90, 100, 130, 145, 160),
    ("cloudy",  "dusk"):   (100,  70,  60, 140, 100,  80),
    ("cloudy",  "night"):  ( 20,  22,  30,  50,  55,  70),
    ("rain",    "dawn"):   ( 80,  90, 110, 110, 120, 145),
    ("rain",    "day"):    ( 40,  55,  75,  80, 105, 135),
    ("rain",    "dusk"):   ( 50,  45,  60,  90,  80, 100),
    ("rain",    "night"):  ( 10,  12,  22,  35,  40,  60),
    ("snow",    "dawn"):   (180, 190, 210, 220, 228, 240),
    ("snow",    "day"):    (140, 160, 190, 190, 210, 230),
    ("snow",    "dusk"):   (120, 110, 140, 180, 165, 195),
    ("snow",    "night"):  ( 15,  18,  35,  60,  70, 110),
    ("thunder", "dawn"):   ( 50,  40,  60,  90,  75, 105),
    ("thunder", "day"):    ( 35,  30,  45,  75,  65,  95),
    ("thunder", "dusk"):   ( 40,  25,  35,  80,  55,  70),
    ("thunder", "night"):  (  8,   8,  18,  30,  30,  55),
}

def time_of_day(hour: int) -> str:
    """Return time-of-day label for a given hour (0–23)."""
    if 5 <= hour < 8:
        return "dawn"
    elif 8 <= hour < 18:
        return "day"
    elif 18 <= hour < 21:
        return "dusk"
    return "night"


# ── Particle definitions ────────────────────────────────────
@dataclass
class Particle:
    row: float
    col: float
    char: str
    speed: float
    drift: float    # horizontal wobble per frame
    r: int
    g: int
    b: int

# Each particle set defines characters, colors, speed, drift, and density.
PARTICLE_SETS = {
    "spring": {
        "chars": ["🌸", "🌺", "✿", "❀", "·"],
        "color_range": [(255, 150, 180), (255, 180, 200), (255, 120, 160)],
        "speed": (0.2, 0.6),
        "drift": (-0.3, 0.3),
        "density": 18,
    },
    "summer_clear": {
        "chars": ["·", "✦", "★", "·", "·"],
        "color_range": [(255, 240, 100), (200, 230, 255), (255, 255, 200)],
        "speed": (0.05, 0.15),
        "drift": (-0.05, 0.05),
        "density": 8,
    },
    "rain": {
        "chars": ["│", "╎", "┊", "⋮", "│"],
        "color_range": [(80, 130, 180), (100, 150, 200), (60, 110, 160)],
        "speed": (0.8, 1.6),
        "drift": (-0.1, 0.1),
        "density": 25,
    },
    "snow": {
        "chars": ["❄", "❅", "❆", "·", "*"],
        "color_range": [(200, 220, 240), (220, 235, 250), (180, 210, 235)],
        "speed": (0.1, 0.35),
        "drift": (-0.2, 0.2),
        "density": 20,
    },
    "thunder": {
        "chars": ["│", "╎", "⋮", "│", "╎"],
        "color_range": [(60, 90, 130), (50, 80, 120), (40, 70, 110)],
        "speed": (1.0, 2.0),
        "drift": (-0.15, 0.15),
        "density": 30,
    },
    "autumn": {
        "chars": ["🍂", "🍁", "◌", "·", "◦"],
        "color_range": [(200, 100, 40), (220, 140, 50), (180, 80, 30)],
        "speed": (0.2, 0.5),
        "drift": (-0.4, 0.4),
        "density": 15,
    },
    "night_clear": {
        "chars": ["·", "✦", "·", "·", "✧"],
        "color_range": [(200, 210, 255), (180, 195, 240), (220, 225, 255)],
        "speed": (0.02, 0.06),
        "drift": (0.0, 0.0),
        "density": 30,
    },
}

def choose_particle_set(state: str, season: str, tod: str) -> str:
    """Pick the right particle set based on weather state, season, and time."""
    if tod == "night" and state == "clear":
        return "night_clear"
    if state in ("rain", "snow", "thunder"):
        return state
    if season == "spring":
        return "spring"
    if season == "autumn":
        return "autumn"
    return "summer_clear"


# ── HTTP helper ─────────────────────────────────────────────
def fetch_json(url: str, timeout: int = 4) -> Optional[dict]:
    """Fetch a URL and return parsed JSON, or None on any error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "openpane/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


# ── Location + weather ──────────────────────────────────────
@dataclass
class LocationInfo:
    city: str
    country: str
    lat: float
    lon: float
    timezone: str

@dataclass
class WeatherInfo:
    state: str      # clear / cloudy / rain / snow / thunder
    season: str     # spring / summer / autumn / winter
    tod: str        # dawn / day / dusk / night
    temp: float
    city: str
    country: str

def get_location() -> Optional[LocationInfo]:
    """Detect current city and coordinates via IP geolocation."""
    data = fetch_json("http://ip-api.com/json/?fields=city,country,lat,lon,timezone,status")
    if data and data.get("status") == "success":
        return LocationInfo(
            city=data.get("city", "Unknown"),
            country=data.get("country", ""),
            lat=float(data.get("lat", 37.5)),
            lon=float(data.get("lon", 127.0)),
            timezone=data.get("timezone", "Asia/Seoul"),
        )
    return None

def get_weather(loc: LocationInfo) -> Optional[WeatherInfo]:
    """Fetch real-time weather from Open-Meteo for the given location."""
    from datetime import datetime, timezone, timedelta

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc.lat}&longitude={loc.lon}"
        f"&current=temperature_2m,weathercode"
        f"&timezone=auto"
    )
    data = fetch_json(url)
    if not data:
        return None

    curr = data.get("current", {})
    code = int(curr.get("weathercode", 0))
    temp = float(curr.get("temperature_2m", 20))

    # Convert UTC offset to local datetime
    offset_seconds = int(data.get("utc_offset_seconds", 0))
    local_dt = datetime.now(timezone(timedelta(seconds=offset_seconds)))
    hour = local_dt.hour
    month = local_dt.month

    return WeatherInfo(
        state=wmo_to_state(code),
        season=get_season(month, loc.lat),
        tod=time_of_day(hour),
        temp=temp,
        city=loc.city,
        country=loc.country,
    )


# ── Renderer ────────────────────────────────────────────────
class WindowRenderer:
    """
    Renders an animated weather scene into the terminal background.
    Particles float down / across the screen based on the current weather.
    """

    def __init__(self, weather: WeatherInfo, rows: int, cols: int):
        self.weather = weather
        self.rows = rows
        self.cols = cols
        self.particles: list[Particle] = []
        self.running = False
        self._lock = threading.Lock()
        self._lightning_timer = 0.0

        # Resolve sky background + foreground colors
        key = (weather.state, weather.tod)
        colors = SKY_COLORS.get(key, SKY_COLORS[("clear", "day")])
        self.bg_r, self.bg_g, self.bg_b = colors[:3]
        self.fg_r, self.fg_g, self.fg_b = colors[3:]

        # Choose and store particle set
        pset_name = choose_particle_set(weather.state, weather.season, weather.tod)
        self.pset = PARTICLE_SETS[pset_name]

        self._init_particles()

    def _init_particles(self):
        """Seed initial particles spread across the screen."""
        for _ in range(self.pset["density"]):
            self.particles.append(self._new_particle(random_row=True))

    def _new_particle(self, random_row: bool = False) -> Particle:
        """Create a new particle, optionally at a random starting row."""
        chars = self.pset["chars"]
        colors = self.pset["color_range"]
        r, g, b = random.choice(colors)
        sp_min, sp_max = self.pset["speed"]
        dr_min, dr_max = self.pset["drift"]
        row = random.uniform(0, self.rows) if random_row else 0.0
        col = random.uniform(0, self.cols)
        return Particle(
            row=row, col=col,
            char=random.choice(chars),
            speed=random.uniform(sp_min, sp_max),
            drift=random.uniform(dr_min, dr_max),
            r=r, g=g, b=b,
        )

    def _render_frame(self):
        """Write one full frame to stdout."""
        out = []
        bg_code = bg(self.bg_r, self.bg_g, self.bg_b)

        # Fill background rows
        for row in range(1, self.rows + 1):
            out.append(move(row, 1))
            out.append(bg_code)
            out.append(" " * self.cols)

        # Draw each particle
        with self._lock:
            for p in self.particles:
                r = int(p.row)
                c = int(p.col)
                if 1 <= r <= self.rows and 1 <= c <= self.cols:
                    out.append(move(r, c))
                    out.append(bg_code + fg(p.r, p.g, p.b))
                    out.append(p.char)

        # Lightning flash effect for thunderstorms
        if self.weather.state == "thunder" and self._lightning_timer > 0:
            lc = random.randint(1, self.cols)
            for lr in range(1, min(8, self.rows)):
                out.append(move(lr, lc + random.randint(-1, 1)))
                out.append(bg(255, 255, 200) + fg(255, 255, 100) + "│")

        # HUD: city, temperature, season — bottom right corner
        season_emoji = {"spring": "🌸", "summer": "☀️", "autumn": "🍂", "winter": "❄️"}
        state_emoji  = {"clear": "☀️", "cloudy": "☁️", "rain": "🌧", "snow": "❄️", "thunder": "⛈"}
        hud = (
            f" {state_emoji.get(self.weather.state, '')} "
            f"{self.weather.city}, {self.weather.country}  "
            f"{self.weather.temp:.0f}°C  "
            f"{season_emoji.get(self.weather.season, '')} "
        )
        hud_col = max(1, self.cols - len(hud))
        out.append(move(self.rows, hud_col))
        out.append(bg(0, 0, 0) + fg(180, 180, 180) + hud)

        out.append(RESET)
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    def _update_particles(self):
        """Advance every particle by one step; recycle those that leave the screen."""
        with self._lock:
            for p in self.particles:
                p.row += p.speed
                p.col += p.drift + random.uniform(-0.05, 0.05)
                # Recycle particle when it goes off-screen
                if p.row > self.rows or p.col < 0 or p.col > self.cols:
                    np = self._new_particle()
                    p.row, p.col = np.row, np.col
                    p.char = np.char
                    p.speed = np.speed
                    p.drift = np.drift

        # Randomly trigger lightning flashes
        if self.weather.state == "thunder":
            self._lightning_timer -= 0.05
            if self._lightning_timer <= 0 and random.random() < 0.02:
                self._lightning_timer = random.uniform(0.1, 0.3)

    def run(self, fps: int = 20):
        """Start the render loop. Blocks until stop() is called."""
        self.running = True
        interval = 1.0 / fps
        sys.stdout.write(HIDE)
        try:
            while self.running:
                self._render_frame()
                self._update_particles()
                time.sleep(interval)
        finally:
            sys.stdout.write(SHOW + RESET)
            sys.stdout.flush()

    def stop(self):
        self.running = False
