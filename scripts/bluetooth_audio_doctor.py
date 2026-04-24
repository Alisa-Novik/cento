#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPORT_DIR = Path.home() / "bluetooth-audio-reports"
DEFAULT_JOURNAL_MINUTES = 15
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3}


@dataclass
class CommandResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def merged_output(self) -> str:
        chunks = [self.stdout.strip(), self.stderr.strip()]
        return "\n".join(chunk for chunk in chunks if chunk).strip()


@dataclass
class Finding:
    severity: str
    title: str
    detail: str


@dataclass
class Action:
    title: str
    status: str
    detail: str


@dataclass
class Diagnosis:
    generated_at: str
    host: str
    target_query: str | None
    target_name: str | None = None
    target_address: str | None = None
    target_info: dict[str, str] = field(default_factory=dict)
    controller_info: dict[str, str] = field(default_factory=dict)
    audio_stack: dict[str, Any] = field(default_factory=dict)
    pulse_cards: list[str] = field(default_factory=list)
    bluetooth_devices: list[dict[str, str]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)


def run_command(cmd: list[str], timeout: int = 20) -> CommandResult:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            cmd=cmd,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return CommandResult(cmd=cmd, returncode=124, stdout=stdout, stderr=stderr)


def run_bluetoothctl(commands: list[str], timeout: int = 20) -> CommandResult:
    payload = "\n".join(commands + ["quit"]) + "\n"
    try:
        completed = subprocess.run(
            ["bluetoothctl"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            cmd=["bluetoothctl"] + commands,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return CommandResult(
            cmd=["bluetoothctl"] + commands,
            returncode=124,
            stdout=stdout,
            stderr=stderr,
        )


def parse_bluetooth_kv(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in {"Device", "Controller"}:
            continue
        parsed[key] = value
    return parsed


def parse_bluetooth_devices(text: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"Device\s+([0-9A-F:]+)\s+(.+)$", line.strip())
        if match:
            devices.append({"address": match.group(1), "name": match.group(2)})
    return devices


def resolve_target(query: str | None, devices: list[dict[str, str]]) -> dict[str, str] | None:
    if not query:
        return None

    query_lower = query.lower()
    exact = [device for device in devices if device["name"].lower() == query_lower]
    if exact:
        return exact[0]

    substring = [device for device in devices if query_lower in device["name"].lower()]
    if substring:
        return substring[0]

    address = [device for device in devices if device["address"].lower() == query_lower]
    if address:
        return address[0]

    return None


def service_state(name: str) -> dict[str, str]:
    active = run_command(["systemctl", "--user", "is-active", name], timeout=10)
    enabled = run_command(["systemctl", "--user", "is-enabled", name], timeout=10)
    return {
        "active": active.merged_output or "unknown",
        "enabled": enabled.merged_output or "unknown",
    }


def collect_audio_stack() -> dict[str, Any]:
    stack: dict[str, Any] = {}
    stack["pulseaudio"] = service_state("pulseaudio.service")
    stack["pulseaudio_socket"] = service_state("pulseaudio.socket")
    stack["pipewire"] = service_state("pipewire.service")
    stack["pipewire_pulse"] = service_state("pipewire-pulse.service")
    stack["wireplumber"] = service_state("wireplumber.service")
    stack["pactl_info"] = run_command(["pactl", "info"], timeout=10).merged_output
    stack["wpctl_status"] = run_command(["wpctl", "status"], timeout=10).merged_output
    stack["pulse_cards"] = run_command(["pactl", "list", "cards", "short"], timeout=10).merged_output
    return stack


def last_logs(target: dict[str, str] | None, minutes: int) -> str:
    patterns = [
        "bluez",
        "bluetoothd",
        "wireplumber",
        "pipewire",
        "pulseaudio",
        "a2dp",
        "headset",
        "sco",
        "avdtp",
        "br-connection-unknown",
        "Connection refused",
    ]
    if target:
        patterns.extend([target["address"], target["name"]])
    regex = "|".join(re.escape(pattern) for pattern in patterns)
    command = (
        f"journalctl -b --no-pager --since '{minutes} minutes ago' "
        f"| rg -i '{regex}'"
    )
    return run_command(["bash", "-lc", command], timeout=20).merged_output


def bluetooth_scan(seconds: int) -> str:
    return run_command(
        ["bluetoothctl", "--timeout", str(seconds), "scan", "on"],
        timeout=max(seconds + 3, 10),
    ).merged_output


def find_card_for_target(pulse_cards: list[str], target: dict[str, str] | None) -> str | None:
    if not target:
        return None
    needle = target["address"].replace(":", "_")
    for line in pulse_cards:
        if needle in line:
            return line
    return None


def add_finding(diagnosis: Diagnosis, severity: str, title: str, detail: str) -> None:
    diagnosis.findings.append(Finding(severity=severity, title=title, detail=detail))


def sorted_findings(diagnosis: Diagnosis) -> list[Finding]:
    return sorted(
        diagnosis.findings,
        key=lambda finding: (SEVERITY_ORDER.get(finding.severity, 99), finding.title.lower()),
    )


def safe_action(
    diagnosis: Diagnosis,
    title: str,
    cmd: list[str] | None = None,
    detail: str | None = None,
) -> CommandResult | None:
    if cmd is None:
        diagnosis.actions.append(Action(title=title, status="skipped", detail=detail or "No command run"))
        return None
    result = run_command(cmd, timeout=20)
    status = "ok" if result.returncode == 0 else "failed"
    diagnosis.actions.append(
        Action(
            title=title,
            status=status,
            detail=result.merged_output or detail or "(no output)",
        )
    )
    return result


def safe_bluetooth_action(diagnosis: Diagnosis, title: str, commands: list[str]) -> CommandResult:
    result = run_bluetoothctl(commands, timeout=25)
    status = "ok" if result.returncode == 0 else "failed"
    diagnosis.actions.append(Action(title=title, status=status, detail=result.merged_output or "(no output)"))
    return result


def diagnose(args: argparse.Namespace) -> Diagnosis:
    generated_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    diagnosis = Diagnosis(
        generated_at=generated_at,
        host=os.uname().nodename,
        target_query=args.device,
    )

    controller = run_command(["bluetoothctl", "show"], timeout=10)
    devices_result = run_command(["bluetoothctl", "devices"], timeout=10)
    paired_result = run_command(["bluetoothctl", "paired-devices"], timeout=10)
    scan_result = bluetooth_scan(args.scan_seconds)

    all_devices = parse_bluetooth_devices("\n".join([devices_result.stdout, paired_result.stdout, scan_result]))
    deduped: dict[str, dict[str, str]] = {device["address"]: device for device in all_devices}
    devices = list(deduped.values())

    diagnosis.controller_info = parse_bluetooth_kv(controller.stdout)
    diagnosis.bluetooth_devices = devices
    diagnosis.evidence["bluetoothctl show"] = controller.merged_output
    diagnosis.evidence["bluetoothctl devices"] = devices_result.merged_output
    diagnosis.evidence["bluetooth scan"] = scan_result

    target = resolve_target(args.device, devices)
    if target:
        target_info_result = run_command(["bluetoothctl", "info", target["address"]], timeout=10)
        diagnosis.target_name = target["name"]
        diagnosis.target_address = target["address"]
        diagnosis.target_info = parse_bluetooth_kv(target_info_result.stdout)
        diagnosis.evidence["bluetoothctl info"] = target_info_result.merged_output
    elif args.device:
        add_finding(
            diagnosis,
            "high",
            "Target device not found",
            f"No Bluetooth device matched query '{args.device}'. Put the device in pairing mode and rescan.",
        )

    diagnosis.audio_stack = collect_audio_stack()
    diagnosis.pulse_cards = [
        line for line in diagnosis.audio_stack.get("pulse_cards", "").splitlines() if line.strip()
    ]
    diagnosis.evidence["pactl info"] = diagnosis.audio_stack.get("pactl_info", "")
    diagnosis.evidence["pactl list cards short"] = diagnosis.audio_stack.get("pulse_cards", "")
    diagnosis.evidence["wpctl status"] = diagnosis.audio_stack.get("wpctl_status", "")

    logs = last_logs(target, args.journal_minutes)
    diagnosis.evidence["journal"] = logs

    controller_powered = diagnosis.controller_info.get("Powered", "").lower()
    if controller_powered != "yes":
        add_finding(
            diagnosis,
            "critical",
            "Bluetooth controller is not powered",
            "The local Bluetooth controller is not powered on, so no device can stay connected.",
        )

    pulse_active = diagnosis.audio_stack["pulseaudio"]["active"] == "active"
    pipewire_active = diagnosis.audio_stack["pipewire"]["active"] == "active"
    wireplumber_active = diagnosis.audio_stack["wireplumber"]["active"] == "active"
    if not pulse_active and not pipewire_active:
        add_finding(
            diagnosis,
            "critical",
            "No active desktop audio daemon",
            "Neither PulseAudio nor PipeWire is active in the user session, so Bluetooth audio devices cannot bind cleanly.",
        )
    elif pipewire_active and not wireplumber_active:
        add_finding(
            diagnosis,
            "high",
            "PipeWire is active without WirePlumber",
            "PipeWire is running but WirePlumber is not, which usually breaks Bluetooth profile negotiation.",
        )
    elif pulse_active and diagnosis.audio_stack["pipewire"]["enabled"] == "masked":
        add_finding(
            diagnosis,
            "info",
            "PulseAudio stack is active",
            "The system is currently using PulseAudio, not PipeWire. That is fine, but Bluetooth repair steps should target PulseAudio rather than PipeWire.",
        )

    if target and diagnosis.target_info:
        connected = diagnosis.target_info.get("Connected", "").lower()
        trusted = diagnosis.target_info.get("Trusted", "").lower()
        paired = diagnosis.target_info.get("Paired", "").lower()
        if paired != "yes":
            add_finding(
                diagnosis,
                "high",
                "Target device is not paired",
                f"{target['name']} is known but not currently paired. Re-pairing is required.",
            )
        if trusted != "yes":
            add_finding(
                diagnosis,
                "medium",
                "Target device is not trusted",
                f"{target['name']} is paired but not trusted, so reconnect behavior may be unreliable.",
            )
        if connected == "yes":
            add_finding(
                diagnosis,
                "info",
                "Target device is currently connected",
                f"{target['name']} reports Connected: yes.",
            )
        else:
            add_finding(
                diagnosis,
                "medium",
                "Target device is not connected",
                f"{target['name']} is known locally but not currently connected.",
            )

        pulse_card = find_card_for_target(diagnosis.pulse_cards, target)
        if pulse_card:
            add_finding(
                diagnosis,
                "info",
                "Audio card exists for target device",
                f"PulseAudio currently exposes card: {pulse_card}",
            )
        elif connected == "yes":
            add_finding(
                diagnosis,
                "high",
                "Target connected without an audio card",
                "The Bluetooth link came up but the desktop audio stack did not create a card for it.",
            )

    if "Connection refused (111)" in logs and target:
        add_finding(
            diagnosis,
            "high",
            "Remote device is rejecting audio profile setup",
            f"{target['name']} is refusing A2DP/HFP profile connections. That usually means it is still owned by another phone/laptop or the pairing record is stale.",
        )
    if "br-connection-unknown" in logs and target:
        add_finding(
            diagnosis,
            "medium",
            "BlueZ reports transport-level disconnects",
            f"BlueZ logged br-connection-unknown while connecting to {target['name']}, which commonly follows a remote-side refusal.",
        )

    return diagnosis


def apply_fixes(args: argparse.Namespace, diagnosis: Diagnosis) -> None:
    target = None
    if diagnosis.target_name and diagnosis.target_address:
        target = {"name": diagnosis.target_name, "address": diagnosis.target_address}

    safe_bluetooth_action(diagnosis, "Ensure Bluetooth controller is powered", ["power on"])

    pulse_active = diagnosis.audio_stack["pulseaudio"]["active"] == "active"
    pipewire_active = diagnosis.audio_stack["pipewire"]["active"] == "active"
    wireplumber_active = diagnosis.audio_stack["wireplumber"]["active"] == "active"

    if pipewire_active or wireplumber_active:
        safe_action(
            diagnosis,
            "Restart PipeWire session services",
            ["systemctl", "--user", "restart", "pipewire.service", "pipewire-pulse.service", "wireplumber.service"],
        )
    elif pulse_active:
        safe_action(
            diagnosis,
            "Restart PulseAudio session services",
            ["systemctl", "--user", "restart", "pulseaudio.service", "pulseaudio.socket"],
        )
    else:
        diagnosis.actions.append(
            Action(
                title="Restart audio session services",
                status="skipped",
                detail="No known user audio service was active, so no restart was attempted.",
            )
        )

    if target:
        if diagnosis.target_info.get("Trusted", "").lower() != "yes":
            safe_bluetooth_action(diagnosis, "Trust target device", [f"trust {target['address']}"])
        safe_bluetooth_action(diagnosis, "Connect target device", [f"connect {target['address']}"])

    if args.repair_pairing and target:
        safe_bluetooth_action(diagnosis, "Remove stale pairing", [f"remove {target['address']}"])
        bluetooth_scan(args.scan_seconds)
        refreshed_devices = parse_bluetooth_devices(run_command(["bluetoothctl", "devices"], timeout=10).stdout)
        refreshed_target = resolve_target(target["name"], refreshed_devices) or resolve_target(target["address"], refreshed_devices)
        if refreshed_target:
            safe_bluetooth_action(
                diagnosis,
                "Re-pair target device",
                [
                    f"pair {refreshed_target['address']}",
                    f"trust {refreshed_target['address']}",
                    f"connect {refreshed_target['address']}",
                ],
            )
        else:
            diagnosis.actions.append(
                Action(
                    title="Re-pair target device",
                    status="skipped",
                    detail="The device did not reappear after scan. Put it into pairing mode and retry.",
                )
            )


def findings_summary(diagnosis: Diagnosis) -> str:
    if not diagnosis.findings:
        return "No significant issues detected."
    highest = sorted_findings(diagnosis)[0].severity
    return f"{len(diagnosis.findings)} findings collected. Highest severity: {highest}."


def render_report(diagnosis: Diagnosis) -> str:
    lines: list[str] = []
    lines.append("# Bluetooth Audio Doctor Report")
    lines.append("")
    lines.append(f"- Generated: `{diagnosis.generated_at}`")
    lines.append(f"- Host: `{diagnosis.host}`")
    if diagnosis.target_query:
        lines.append(f"- Query: `{diagnosis.target_query}`")
    if diagnosis.target_name and diagnosis.target_address:
        lines.append(f"- Resolved target: `{diagnosis.target_name}` (`{diagnosis.target_address}`)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(findings_summary(diagnosis))
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if diagnosis.findings:
        for finding in sorted_findings(diagnosis):
            lines.append(f"- `{finding.severity.upper()}` {finding.title}: {finding.detail}")
    else:
        lines.append("- No findings.")
    lines.append("")
    lines.append("## Actions")
    lines.append("")
    if diagnosis.actions:
        for action in diagnosis.actions:
            lines.append(f"- `{action.status.upper()}` {action.title}: {action.detail}")
    else:
        lines.append("- No repair actions were run.")
    lines.append("")
    lines.append("## Audio Stack")
    lines.append("")
    for name in ("pulseaudio", "pulseaudio_socket", "pipewire", "pipewire_pulse", "wireplumber"):
        state = diagnosis.audio_stack.get(name, {})
        if isinstance(state, dict):
            lines.append(f"- `{name}` active=`{state.get('active', 'unknown')}` enabled=`{state.get('enabled', 'unknown')}`")
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    for title, body in diagnosis.evidence.items():
        if not body:
            continue
        lines.append(f"### {title}")
        lines.append("")
        lines.append("```text")
        lines.append(body.strip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def default_report_path(target_query: str | None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = re.sub(r"[^a-z0-9]+", "-", (target_query or "general").lower()).strip("-") or "general"
    return REPORT_DIR / f"{stamp}-{suffix}.md"


def as_jsonable(diagnosis: Diagnosis) -> dict[str, Any]:
    return {
        "generated_at": diagnosis.generated_at,
        "host": diagnosis.host,
        "target_query": diagnosis.target_query,
        "target_name": diagnosis.target_name,
        "target_address": diagnosis.target_address,
        "target_info": diagnosis.target_info,
        "controller_info": diagnosis.controller_info,
        "audio_stack": diagnosis.audio_stack,
        "pulse_cards": diagnosis.pulse_cards,
        "bluetooth_devices": diagnosis.bluetooth_devices,
        "findings": [finding.__dict__ for finding in diagnosis.findings],
        "actions": [action.__dict__ for action in diagnosis.actions],
        "evidence": diagnosis.evidence,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Bluetooth/audio diagnostics, write a detailed report, and apply safe repairs."
    )
    parser.add_argument("device", nargs="?", help="Bluetooth device name substring or MAC address")
    parser.add_argument("--fix", action="store_true", help="Apply safe, non-destructive repair actions")
    parser.add_argument(
        "--repair-pairing",
        action="store_true",
        help="Remove the current pairing and try to pair/trust/connect again",
    )
    parser.add_argument(
        "--journal-minutes",
        type=int,
        default=DEFAULT_JOURNAL_MINUTES,
        help="How far back to inspect logs",
    )
    parser.add_argument(
        "--scan-seconds",
        type=int,
        default=8,
        help="How long to scan for Bluetooth advertisements",
    )
    parser.add_argument("--report", help="Path to write the Markdown report")
    parser.add_argument("--json", action="store_true", help="Print the diagnosis as JSON to stdout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    diagnosis = diagnose(args)
    if args.fix or args.repair_pairing:
        apply_fixes(args, diagnosis)
        diagnosis = diagnose(args)

    report_body = render_report(diagnosis)
    report_path = Path(args.report).expanduser() if args.report else default_report_path(args.device)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_body)

    if args.json:
        print(json.dumps(as_jsonable(diagnosis), indent=2))
    else:
        print(report_body)
        print(f"Report saved to: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
