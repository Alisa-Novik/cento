#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any


STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento" / "industrial-os"
NET_STATE_FILE = STATE_DIR / "net.json"


def read_cpu() -> tuple[int, int]:
    parts = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]
    values = [int(item) for item in parts]
    idle = values[3] + values[4]
    return sum(values), idle


def cpu_percent() -> int:
    total_a, idle_a = read_cpu()
    time.sleep(0.06)
    total_b, idle_b = read_cpu()
    total_delta = max(total_b - total_a, 1)
    idle_delta = max(idle_b - idle_a, 0)
    return round((1 - idle_delta / total_delta) * 100)


def memory_percent() -> int:
    data: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", 1)
        data[key] = int(value.strip().split()[0])
    total = data.get("MemTotal", 1)
    available = data.get("MemAvailable", data.get("MemFree", 0))
    return round((1 - available / total) * 100)


def disk_percent() -> int:
    usage = shutil.disk_usage("/")
    return round((usage.used / usage.total) * 100)


def temperatures() -> list[int]:
    values: list[int] = []
    for pattern in ("/sys/class/hwmon/hwmon*/temp*_input", "/sys/class/thermal/thermal_zone*/temp"):
        for path in Path("/").glob(pattern.lstrip("/")):
            try:
                raw = int(path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
            value = round(raw / 1000)
            if 0 < value < 120:
                values.append(value)
    return values


def temperature_c() -> int:
    values = temperatures()
    return max(values) if values else 0


def read_net_bytes() -> tuple[int, int]:
    rx_total = 0
    tx_total = 0
    for path in Path("/sys/class/net").iterdir():
        if path.name == "lo":
            continue
        try:
            state = (path / "operstate").read_text(encoding="utf-8").strip()
            rx = int((path / "statistics" / "rx_bytes").read_text(encoding="utf-8").strip())
            tx = int((path / "statistics" / "tx_bytes").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        if state in {"up", "unknown"}:
            rx_total += rx
            tx_total += tx
    return rx_total, tx_total


def net_rates() -> tuple[float, float]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    now = time.time()
    rx, tx = read_net_bytes()
    previous: dict[str, Any] = {}
    try:
        previous = json.loads(NET_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    NET_STATE_FILE.write_text(json.dumps({"time": now, "rx": rx, "tx": tx}), encoding="utf-8")
    then = float(previous.get("time") or 0)
    if then <= 0 or now <= then:
        return 0.0, 0.0
    seconds = now - then
    return max(0.0, (rx - int(previous.get("rx") or rx)) / seconds), max(0.0, (tx - int(previous.get("tx") or tx)) / seconds)


def format_rate(value: float) -> str:
    units = ["B", "K", "M", "G"]
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)}{units[index]}"
    return f"{value:.1f}{units[index]}"


def job_summary() -> str:
    try:
        from jobs_server import load_jobs

        jobs = load_jobs().get("jobs", [])
    except Exception:
        jobs = []
    active_statuses = {"planned", "running", "dry-run", "dry_run", "queued"}
    active = sum(1 for job in jobs if str(job.get("status", "")).lower() in active_statuses)
    failed = sum(1 for job in jobs if str(job.get("status", "")).lower() == "failed")
    if failed:
        return f"JOBS {len(jobs)} FAIL {failed}"
    if active:
        return f"JOBS {len(jobs)} ACTIVE {active}"
    return f"JOBS {len(jobs)}"


def metrics() -> dict[str, Any]:
    down, up = net_rates()
    return {
        "cpu": cpu_percent(),
        "ram": memory_percent(),
        "disk": disk_percent(),
        "temp": temperature_c(),
        "net_down": format_rate(down),
        "net_up": format_rate(up),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print Industrial OS status metrics.")
    parser.add_argument("--polybar", action="store_true", help="Print compact Polybar text.")
    parser.add_argument("--jobs", action="store_true", help="Print compact cluster job text.")
    parser.add_argument("--json", action="store_true", help="Print JSON metrics.")
    args = parser.parse_args()

    if args.jobs:
        print(job_summary())
        return 0

    data = metrics()
    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    if args.polybar:
        print(
            f"CPU {data['cpu']}% | RAM {data['ram']}% | DISK {data['disk']}% | "
            f"TEMP {data['temp']}C | NET {data['net_down']} down {data['net_up']} up"
        )
        return 0

    for key, value in data.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
