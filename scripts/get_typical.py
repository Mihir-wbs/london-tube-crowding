"""Download TfL's typical crowding pattern (one-off) for every station in
collect.py: 7 days x 96 fifteen-minute bands per station.
Saves data/reference/typical_crowding.csv for comparison with live data."""
import csv
from pathlib import Path

from collect import STATIONS, TFL, get_json

OUT = Path("data/reference/typical_crowding.csv")
FIELDS = ["naptan", "station", "day_of_week", "time_band", "band_start",
          "typical_pct", "am_peak_band", "pm_peak_band"]


def main():
    rows = []
    for code, name in STATIONS.items():
        try:
            d = get_json(f"{TFL}/crowding/{code}")
        except Exception as e:
            print(f"{name}: request failed ({e})")
            continue
        if not d.get("isFound"):
            print(f"{name}: no typical pattern available")
            continue
        for day in d.get("daysOfWeek", []):
            for band in day.get("timeBands", []):
                rows.append({
                    "naptan": code,
                    "station": name,
                    "day_of_week": day.get("dayOfWeek"),
                    "time_band": band.get("timeBand"),
                    "band_start": band.get("timeBand", "")[:5],
                    "typical_pct": band.get("percentageOfBaseLine"),
                    "am_peak_band": day.get("amPeakTimeBand"),
                    "pm_peak_band": day.get("pmPeakTimeBand"),
                })
        print(f"{name}: ok")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
