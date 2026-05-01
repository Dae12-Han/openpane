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
        _print_help()
        return

    if cmd == "on":
        _run()
    elif cmd == "set-city":
        if len(args) < 2:
            print("usage: openpane set-city <city name>")
            print("example: openpane set-city Daejeon")
            return
        _set_city(" ".join(args[1:]))
    elif cmd == "reset":
        _reset_config()
    else:
        print(f"unknown command: {cmd}")
        print("  run `openpane --help` for usage")


def _print_help():
    print("openpane 🌸  —  open the pane, see the world beyond your terminal")
    print()
    print("  openpane on              open the window")
    print("  openpane set-city CITY   set your city manually (e.g. Daejeon)")
    print("  openpane reset           clear saved location")
    print("  openpane --help          show this help message")


def _set_city(city_name: str):
    """Save a manual city to config."""
    from .core import geocode_city, save_config

    print(f"🔍 looking up '{city_name}'...")
    loc = geocode_city(city_name)
    if not loc:
        print(f"❌ couldn't find '{city_name}'. try a different spelling?")
        return

    save_config({
        "city": loc.city,
        "country": loc.country,
        "lat": loc.lat,
        "lon": loc.lon,
        "timezone": loc.timezone,
    })
    print(f"✅ saved! openpane will use {loc.city}, {loc.country} from now on.")


def _reset_config():
    """Delete saved config."""
    from .core import CONFIG_PATH
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        print("✅ location reset. openpane will detect your location again next time.")
    else:
        print("nothing to reset.")


def _run():
    from .core import (
        get_location, get_location_by_ip, geocode_city, get_weather,
        WeatherInfo, WindowRenderer, RESET, time_of_day,
        load_config, save_config,
    )
    import datetime

    cols, rows = shutil.get_terminal_size((80, 24))
    rows = max(rows, 12)

    config = load_config()
    is_first_run = "city" not in config

    if is_first_run:
        # First run — detect location and confirm with user
        print("🌍 detecting your location...")
        detected = get_location_by_ip()

        if detected:
            print(f"📍 detected: {detected.city}, {detected.country}")
            try:
                answer = input("   correct? [Y/n]: ").strip().lower()
            except EOFError:
                answer = "y"

            if answer in ("", "y", "yes"):
                save_config({
                    "city": detected.city,
                    "country": detected.country,
                    "lat": detected.lat,
                    "lon": detected.lon,
                    "timezone": detected.timezone,
                })
                loc = detected
            else:
                try:
                    city_name = input("   enter your city: ").strip()
                except EOFError:
                    city_name = ""

                if not city_name:
                    print("⚠️  no city given. using detected location.")
                    save_config({
                        "city": detected.city,
                        "country": detected.country,
                        "lat": detected.lat,
                        "lon": detected.lon,
                        "timezone": detected.timezone,
                    })
                    loc = detected
                else:
                    print(f"🔍 looking up '{city_name}'...")
                    found = geocode_city(city_name)
                    if found:
                        save_config({
                            "city": found.city,
                            "country": found.country,
                            "lat": found.lat,
                            "lon": found.lon,
                            "timezone": found.timezone,
                        })
                        loc = found
                        print(f"✅ saved: {found.city}, {found.country}")
                    else:
                        print(f"❌ couldn't find '{city_name}'. using detected location.")
                        save_config({
                            "city": detected.city,
                            "country": detected.country,
                            "lat": detected.lat,
                            "lon": detected.lon,
                            "timezone": detected.timezone,
                        })
                        loc = detected
        else:
            print("⚠️  couldn't detect location automatically.")
            try:
                city_name = input("   enter your city: ").strip()
            except EOFError:
                city_name = "Seoul"

            found = geocode_city(city_name) if city_name else None
            if found:
                save_config({
                    "city": found.city,
                    "country": found.country,
                    "lat": found.lat,
                    "lon": found.lon,
                    "timezone": found.timezone,
                })
                loc = found
            else:
                class _FallbackLoc:
                    city = "Seoul"; country = "KR"
                    lat = 37.5;     lon = 127.0
                    timezone = "Asia/Seoul"
                loc = _FallbackLoc()
                print("⚠️  using Seoul as fallback.")
    else:
        # Returning user — use saved location
        loc = get_location()
        print(f"📍 {loc.city}, {loc.country}")

    print("🌤  fetching weather...")
    weather = get_weather(loc)

    if not weather:
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
        renderer.stop()
        sys.stdout.write(RESET)
        print("\n🌸 window closed. good work today.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_exit)
    signal.signal(signal.SIGTERM, _on_exit)

    t = renderer.run(fps=20)
    t.join()


if __name__ == "__main__":
    main()