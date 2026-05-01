"""
openpane CLI — entry point for the `openpane` command.
"""

import sys

from .core import (
    get_location, get_weather, WeatherInfo,
    pick_asset, time_of_day,
)
from .backends import get_backend, diagnose
from .generator import generate_gif, generate_png, clear_cache, HAS_PIL


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "on"

    if cmd in ("-h", "--help", "help"):
        _print_help()
        return

    if cmd == "on":
        _cmd_on()
    elif cmd == "off":
        _cmd_off()
    elif cmd == "doctor":
        _cmd_doctor()
    elif cmd == "clear-cache":
        clear_cache()
        print("🧹 cache cleared")
    else:
        print(f"unknown command: {cmd}")
        _print_help()


def _print_help():
    print("openpane 🌸  —  open the pane, see the world beyond your terminal")
    print()
    print("  openpane on            apply weather background")
    print("  openpane off           remove background")
    print("  openpane doctor        diagnose your environment")
    print("  openpane clear-cache   delete cached background images")
    print("  openpane --help        show this help")


def _cmd_doctor():
    print(diagnose())
    print(f"   Pillow installed: {'yes' if HAS_PIL else 'no'}")


def _cmd_on():
    # Check Pillow is installed (required to generate images)
    if not HAS_PIL:
        print("❌ Pillow is required to generate background images.")
        print("   Install with: pip install Pillow")
        sys.exit(1)

    # Resolve backend
    backend = get_backend()
    if backend is None:
        print(diagnose())
        print()
        print("openpane currently supports:")
        print("  • macOS + iTerm2")
        print("  • Windows + Windows Terminal")
        sys.exit(1)

    print(f"🖥  using {backend.name} backend")

    # Detect location
    print("🌍 detecting location...")
    loc = get_location()
    if not loc:
        class _FallbackLoc:
            city = "Seoul"; country = "KR"
            lat = 37.5;     lon = 127.0
            timezone = "Asia/Seoul"
        loc = _FallbackLoc()
        print("⚠️  location unavailable — defaulting to Seoul")

    print(f"📍 {loc.city}, {loc.country}")

    # Fetch weather
    print("🌤  fetching weather...")
    weather = get_weather(loc)
    if not weather:
        import datetime
        hour = datetime.datetime.now().hour
        weather = WeatherInfo(
            state="clear", season="spring",
            tod=time_of_day(hour),
            temp=20.0, city=loc.city, country=loc.country,
        )
        print("⚠️  weather unavailable — defaulting to clear sky")

    print(f"🌡  {weather.temp:.0f}°C  {weather.state}  {weather.season}")

    # Generate or fetch cached image
    asset = pick_asset(weather)
    print(f"🖼  preparing background: {asset}.{backend.image_format}")
    print("   (first run may take a few seconds — cached afterwards)")

    try:
        if backend.image_format == "gif":
            image_path = generate_gif(asset)
        else:
            image_path = generate_png(asset)
    except Exception as e:
        print(f"❌ failed to generate image: {e}")
        sys.exit(1)

    # Apply via the backend
    if backend.apply(image_path):
        print()
        print("🌸 your window is open. happy coding!")
        print("   run `openpane off` to remove the background.")
    else:
        print(f"❌ failed to apply background via {backend.name}.")
        sys.exit(1)


def _cmd_off():
    backend = get_backend()
    if backend is None:
        print(diagnose())
        sys.exit(1)

    if backend.clear():
        print("🪟 window closed. good work today.")
    else:
        print(f"❌ failed to clear background via {backend.name}.")
        sys.exit(1)


if __name__ == "__main__":
    main()
