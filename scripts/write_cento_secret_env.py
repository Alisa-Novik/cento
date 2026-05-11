#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import stat
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: write_cento_secret_env.py PATH", file=sys.stderr)
        return 2
    raw = sys.stdin.buffer.read()
    try:
        api_key_raw, model_raw = raw.split(b"\0", 1)
    except ValueError:
        print("expected NUL-separated key and model on stdin", file=sys.stderr)
        return 2
    api_key = api_key_raw.decode("utf-8")
    model = model_raw.decode("utf-8")
    if not api_key:
        print("OPENAI_API_KEY is required", file=sys.stderr)
        return 2
    if not model:
        print("CENTO_OPENAI_WORKER_MODEL is required", file=sys.stderr)
        return 2

    path = Path(argv[1]).expanduser()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass

    existing: list[str] = []
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            existing = []

    managed = {"OPENAI_API_KEY", "CENTO_OPENAI_WORKER_MODEL"}
    kept: list[str] = []
    for line in existing:
        stripped = line.strip()
        probe = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        key = probe.split("=", 1)[0].strip() if "=" in probe else ""
        if key in managed:
            continue
        kept.append(line)

    if kept and kept[-1].strip():
        kept.append("")
    kept.extend(
        [
            "# Managed by `cento temp run openai-key`.",
            f"export OPENAI_API_KEY={shlex.quote(api_key)}",
            f"export CENTO_OPENAI_WORKER_MODEL={shlex.quote(model)}",
        ]
    )

    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(kept).rstrip() + "\n")
    os.replace(tmp, path)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
