"""
Simple day/night light scheduler.

Day mode sets lights to cool white at 5500K.
Night mode sets lights to a configured RGB color.
"""

import argparse
import datetime as dt
import os
import sys

import requests


def parse_time(value):
    """Parse HH:MM into a time object."""
    try:
        return dt.datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Time must be HH:MM (24-hour).") from exc


def parse_rgb(value):
    """Parse RGB triplet as R,G,B."""
    try:
        red, green, blue = [int(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("RGB must be in the form R,G,B.") from exc
    channels = (red, green, blue)
    if any(channel < 0 or channel > 255 for channel in channels):
        raise argparse.ArgumentTypeError("Each RGB channel must be between 0 and 255.")
    return channels


def parse_day_kelvin(value):
    """Parse daytime Kelvin value."""
    try:
        kelvin = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Kelvin must be an integer.") from exc
    if kelvin < 1000 or kelvin > 20000:
        raise argparse.ArgumentTypeError("Kelvin must be between 1000 and 20000.")
    return kelvin


def parse_brightness(value):
    """Parse brightness percentage."""
    try:
        brightness = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Brightness must be an integer.") from exc
    if brightness < 1 or brightness > 100:
        raise argparse.ArgumentTypeError("Brightness must be between 1 and 100.")
    return brightness


def is_night(now_time, day_start, night_start):
    """Return True when current time falls in the configured night window."""
    if day_start < night_start:
        return now_time < day_start or now_time >= night_start
    return night_start <= now_time < day_start


def apply_home_assistant(url, token, entities, payload):
    """Apply payload to Home Assistant light entities."""
    endpoint = f"{url.rstrip('/')}/api/services/light/turn_on"
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    for entity in entities:
        data = {"entity_id": entity, **payload}
        try:
            response = requests.post(endpoint, headers=headers, json=data, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            status_code = exc.response.status_code if exc.response is not None else "n/a"
            details = exc.response.text if exc.response is not None else str(exc)
            raise RuntimeError(
                f"entity '{entity}' failed with status {status_code}: {details}"
            ) from exc


def main():
    parser = argparse.ArgumentParser(
        description="Set lights to cool white by day and color by night."
    )
    parser.add_argument("--day-start", type=parse_time, default=parse_time("07:00"))
    parser.add_argument("--night-start", type=parse_time, default=parse_time("20:00"))
    parser.add_argument(
        "--night-rgb",
        type=parse_rgb,
        default=parse_rgb("255,80,0"),
        help="Night color as R,G,B (0-255), default: 255,80,0",
    )
    parser.add_argument(
        "--day-kelvin",
        type=parse_day_kelvin,
        default=parse_day_kelvin("5500"),
        help="Daytime color temperature in Kelvin, default: 5500",
    )
    parser.add_argument(
        "--night-brightness",
        type=parse_brightness,
        default=parse_brightness("30"),
        help="Night brightness percent (1-100), default: 30",
    )
    parser.add_argument(
        "--ha-url",
        default=os.environ.get("HOME_ASSISTANT_URL"),
        help="Home Assistant base URL, e.g. http://homeassistant.local:8123",
    )
    parser.add_argument(
        "--ha-token",
        default=os.environ.get("HOME_ASSISTANT_TOKEN"),
        help="Home Assistant long-lived access token",
    )
    parser.add_argument(
        "--entity",
        action="append",
        default=[],
        help="Light entity id(s), e.g. --entity light.living_room",
    )

    args = parser.parse_args()
    now_time = dt.datetime.now().time()
    night_mode = is_night(now_time, args.day_start, args.night_start)
    payload = (
        {"rgb_color": list(args.night_rgb), "brightness_pct": args.night_brightness}
        if night_mode
        else {"color_temp_kelvin": args.day_kelvin, "brightness_pct": 100}
    )

    mode = "night color mode" if night_mode else f"day cool-white mode ({args.day_kelvin}K)"
    print(f"Current mode: {mode}")
    print(f"Payload: {payload}")

    if not args.ha_url or not args.ha_token or not args.entity:
        print(
            "Dry run only. Provide --ha-url, --ha-token, and at least one --entity "
            "to apply settings to real lights."
        )
        return

    try:
        apply_home_assistant(args.ha_url, args.ha_token, args.entity, payload)
    except RuntimeError as exc:
        print(f"Failed to apply light settings: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Updated {len(args.entity)} light(s).")


if __name__ == "__main__":
    main()
