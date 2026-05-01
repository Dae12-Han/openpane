"""
openpane CLI
Entry point for the `openpane` command.
"""

import sys
import os
import shutil
import signal
import time


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "on"

    if cmd in ("-h", "--help", "help"):
        print("openpane 🌸  —  open the pane, see the world beyond your terminal")
        print()
        print("  openpane on      open the window (auto-detects location & weather)")
        print("  openpane --help  show this help message")
        return

    if cmd == "on":
        _run()
    else:
        print(f"unknown command: {cmd}")
        print("  run `openpane --help` for usage")


def _run():
    from .core import (
        get_location, get_weather, WeatherInfo,
        WindowRenderer, RESET, time_of_day
    )
    import datetime

    cols, rows = shutil.get_terminal_size((80, 24))
    rows = max(rows - 1, 5)

    print("🌍 detecting location...")
    loc = get_location()

    if not loc:
        # Offline fallback — default to Seoul
        class _FallbackLoc:
            city = "Seoul"; country = "KR"
            lat = 37.5;     lon = 127.0
            timezone = "Asia/Seoul"
        loc = _FallbackLoc()
        print("⚠️  location unavailable — defaulting to Seoul")

    print(f"📍 {loc.city}, {loc.country}")
    print("🌤  fetching weather...")

    weather = get_weather(loc)

    if not weather:
        # Weather fallback — clear sky
        hour = datetime.datetime.now().hour
        weather = WeatherInfo(
            state="clear",
            season="spring",
            tod=time_of_day(hour),
            temp=20.0,
            city=loc.city,
            country=loc.country,
        )
        print("⚠️  weather unavailable — defaulting to clear sky")

    print(f"🌡  {weather.temp:.0f}°C  {weather.state}  {weather.season}")
    print()
    print("opening your window... (press Ctrl+C to close)")
    time.sleep(1.2)

    renderer = WindowRenderer(weather, rows, cols)

    def _on_exit(sig, frame):
        """Clean up terminal and exit gracefully on Ctrl+C or SIGTERM."""
        renderer.stop()
        sys.stdout.write(RESET)
        os.system("clear" if os.name != "nt" else "cls")
        print("🌸 window closed. good work today.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_exit)
    signal.signal(signal.SIGTERM, _on_exit)

    renderer.run(fps=20)


if __name__ == "__main__":
    main()
