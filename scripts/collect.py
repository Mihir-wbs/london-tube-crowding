"""Collect one snapshot of TfL crowding, line status and London weather.
Run every 15 minutes by GitHub Actions. Appends rows to daily CSV files."""
import csv
import datetime as dt
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TFL = "https://api.tfl.gov.uk"
KEY = os.environ.get("TFL_APP_KEY", "")
LONDON = ZoneInfo("Europe/London")
END_DATE = dt.date(2026, 11, 8)          # last day of the 30-day window

# NaPTAN code -> station name (tube stations only)
STATIONS = {
    "940GZZLUWLO": "Waterloo",            # commuter hub
    "940GZZLULVT": "Liverpool Street",    # commuter hub
    "940GZZLUBNK": "Bank",                # City offices
    "940GZZLUCYF": "Canary Wharf",        # offices
    "940GZZLUKSX": "King's Cross St Pancras",  # rail interchange
    "940GZZLUVIC": "Victoria",            # rail interchange
    "940GZZLUOXC": "Oxford Circus",       # shopping
    "940GZZLULSQ": "Leicester Square",    # nightlife / theatres
    "940GZZLUSTD": "Stratford",           # shopping + West Ham
    "940GZZLUWSM": "Westminster",         # tourists
    "940GZZLUWYP": "Wembley Park",        # stadium events
    "940GZZLUASL": "Arsenal",             # football
}

CROWD_FIELDS = ["fetched_utc", "naptan", "station", "data_available",
                "pct_of_baseline", "tfl_time_utc", "error"]
STATUS_FIELDS = ["fetched_utc", "line_id", "line_name", "mode",
                 "severity", "status", "reason"]
WEATHER_FIELDS = ["fetched_utc", "temp_c", "precip_mm", "weather_code"]


def get_json(url, params=None, use_key=True):
    params = dict(params or {})
    if use_key and KEY:
        params["app_key"] = KEY
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def append_rows(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def main():
    now = dt.datetime.now(dt.timezone.utc)
    local_day = now.astimezone(LONDON).date()
    if local_day > END_DATE:
        print("Collection window is over. Nothing to do.")
        return 0

    stamp = now.isoformat(timespec="seconds")
    day = local_day.isoformat()
    failures = 0

    # 1) Crowding: one request per station
    crowd_rows = []
    for code, name in STATIONS.items():
        row = {"fetched_utc": stamp, "naptan": code, "station": name, "error": ""}
        try:
            d = get_json(f"{TFL}/crowding/{code}/Live")
            row.update(data_available=d.get("dataAvailable"),
                       pct_of_baseline=d.get("percentageOfBaseline"),
                       tfl_time_utc=d.get("timeUtc"))
        except Exception as e:
            failures += 1
            row["error"] = str(e)[:200]
        crowd_rows.append(row)
    append_rows(Path(f"data/raw/crowding/{day}.csv"), crowd_rows, CROWD_FIELDS)

    # 2) Line status: one request for all rail lines
    try:
        lines = get_json(f"{TFL}/Line/Mode/tube,elizabeth-line,overground,dlr/Status")
        status_rows = [
            {"fetched_utc": stamp, "line_id": ln["id"], "line_name": ln["name"],
             "mode": ln["modeName"], "severity": s.get("statusSeverity"),
             "status": s.get("statusSeverityDescription"),
             "reason": " ".join((s.get("reason") or "").split())}
            for ln in lines for s in ln.get("lineStatuses", [])
        ]
        append_rows(Path(f"data/raw/status/{day}.csv"), status_rows, STATUS_FIELDS)
    except Exception as e:
        failures += 1
        print("Line status failed:", e)

    # 3) Weather in central London (Open-Meteo, no key needed)
    try:
        w = get_json("https://api.open-meteo.com/v1/forecast",
                     {"latitude": 51.5072, "longitude": -0.1276,
                      "current": "temperature_2m,precipitation,weather_code"},
                     use_key=False)["current"]
        append_rows(Path(f"data/raw/weather/{day}.csv"),
                    [{"fetched_utc": stamp, "temp_c": w.get("temperature_2m"),
                      "precip_mm": w.get("precipitation"),
                      "weather_code": w.get("weather_code")}], WEATHER_FIELDS)
    except Exception as e:
        failures += 1
        print("Weather failed:", e)

    print(f"{stamp}: saved {len(crowd_rows)} crowding rows, {failures} failures")
    # Fail the run (red X in GitHub) only if everything failed
    return 1 if failures >= len(STATIONS) + 2 else 0


if __name__ == "__main__":
    sys.exit(main())