#!/usr/bin/env python3
"""Download and normalize the latest CFTC COT futures reports.

This first implementation deliberately preserves source metadata and raw
category fields. It does not turn positioning into a trading signal.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

YEAR = datetime.now(timezone.utc).year
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cot-feed.json"

URLS = [
    f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{YEAR}.zip",
    f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{YEAR}.zip",
]


def download(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "MacroTerminal/1.0"})
    with urlopen(req, timeout=45) as response:
        return response.read()


def clean(value: str | None):
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return value


def normalize_row(row: dict[str, str]):
    result = {}
    for key, value in row.items():
        key = re.sub(r"\s+", " ", key.strip().lower())
        result[key] = clean(value)
    return result


def read_zip(payload: bytes):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if not names:
            return []
        with archive.open(names[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
            sample = text.read(4096)
            text.seek(0)
            dialect = csv.Sniffer().sniff(sample)
            return [normalize_row(row) for row in csv.DictReader(text, dialect=dialect)]


def main():
    reports = []
    errors = []
    for url in URLS:
        try:
            rows = read_zip(download(url))
            reports.append({"source": url, "rows": rows})
        except Exception as exc:  # keep the feed valid even if one CFTC file changes
            errors.append({"source": url, "error": str(exc)})

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output = {
        "schemaVersion": 1,
        "source": "CFTC",
        "lastUpdated": now,
        "dataTimestamp": now,
        "status": "ok" if reports else "error",
        "coverage": {"year": YEAR, "reports": len(reports)},
        "delay": "official COT publication delay",
        "method": "CFTC annual compressed text files; fields preserved after normalization",
        "reports": reports,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    if not reports:
        raise SystemExit("CFTC download failed: " + json.dumps(errors))
    print(f"Wrote {OUT} with {len(reports)} report files")


if __name__ == "__main__":
    main()
