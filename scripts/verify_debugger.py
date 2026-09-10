#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path("/app")
RECORDINGS = ROOT / "debug-recording"

DEMOS = {
    "runtime-state": {
        "recording": RECORDINGS / "runtime-state.retrace",
        "source": ROOT / "tests" / "test_order_metrics.py",
        "line": 31,
        "locals": {"retained_units", "net_revenue_cents", "runtime_incident_evidence"},
        "replay_text": "ZeroDivisionError",
    },
}


def replay_binary(recording: Path) -> str:
    with recording.open("rb") as stream:
        shebang = stream.readline().decode("ascii").strip()
    if not shebang.startswith("#!"):
        raise AssertionError(f"{recording} has no replay shebang")
    return shebang[2:].split()[0]


def environment_check() -> None:
    if sys.version_info[:3] != (3, 12, 13):
        raise AssertionError(f"expected Python 3.12.13, got {sys.version.split()[0]}")

    versions = subprocess.run(
        [sys.executable, "-m", "pip", "show", "retracesoftware", "retracesoftware-dap"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout
    if versions.count("Version: 0.2.30") != 2:
        raise AssertionError(f"unexpected Retrace package versions:\n{versions}")

    print("environment=pass python=3.12.13 retracesoftware=0.2.30 dap=0.2.30")


def recording_check(demo: dict[str, Any]) -> None:
    recording = demo["recording"]
    source = demo["source"]
    if not recording.is_file() or recording.stat().st_size == 0:
        raise AssertionError(
            f"missing recording: {recording}\nRun 'make run' on the host first."
        )
    if not source.is_file():
        raise AssertionError(f"missing source: {source}")
    binary = Path(replay_binary(recording))
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise AssertionError(f"recording replay binary is unavailable: {binary}")


def live_demo(recording: Path) -> dict[str, Any]:
    demo = dict(DEMOS["runtime-state"])
    demo["recording"] = recording
    payload_path = ROOT / "reports" / "runtime-payload.json"
    if not payload_path.is_file():
        raise AssertionError(
            f"missing runtime payload: {payload_path}\nRun 'make run' on the host first."
        )
    payload = json.loads(payload_path.read_text())
    order = next(
        item
        for item in payload["orders"]
        if int(item["shipped_units"]) == int(item["returned_units"])
    )
    retained_units = int(order["shipped_units"]) - int(order["returned_units"])
    net_revenue_cents = int(order["gross_revenue_cents"]) - int(
        order["refunded_revenue_cents"]
    )
    demo["expected_values"] = {
        "retained_units": str(retained_units),
        "net_revenue_cents": str(net_revenue_cents),
        "runtime_incident_evidence": (
            f"batch_id={payload['batch_id']} order_id={order['order_id']} "
            f"customer_id={order['customer_id']}"
        ),
    }
    return demo


class DAPClient:
    def __init__(self, recording: Path, pid: int) -> None:
        self.sequence = 1
        self.messages: list[dict[str, Any]] = []
        self.process = subprocess.Popen(
            [
                replay_binary(recording),
                "--recording",
                str(recording),
                "--dap",
                "--pid",
                str(pid),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

    def send(self, command: str, arguments: dict[str, Any] | None = None) -> int:
        assert self.process.stdin is not None
        sequence = self.sequence
        self.sequence += 1
        message = {
            "seq": sequence,
            "type": "request",
            "command": command,
            "arguments": arguments or {},
        }
        payload = json.dumps(message, separators=(",", ":")).encode()
        self.process.stdin.write(f"Content-Length: {len(payload)}\r\n\r\n".encode())
        self.process.stdin.write(payload)
        self.process.stdin.flush()
        return sequence

    def read(self, timeout: float = 45) -> dict[str, Any]:
        assert self.process.stdout is not None
        deadline = time.monotonic() + timeout
        headers: dict[str, str] = {}
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out waiting for DAP headers")
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            if not ready:
                raise TimeoutError("timed out waiting for DAP message")
            line = self.process.stdout.readline()
            if not line:
                stderr = self.process.stderr.read().decode(errors="replace") if self.process.stderr else ""
                raise RuntimeError(f"DAP process exited early: {stderr}")
            if line == b"\r\n":
                break
            key, value = line.decode("ascii").split(":", 1)
            headers[key.lower()] = value.strip()

        length = int(headers["content-length"])
        payload = self.process.stdout.read(length)
        message = json.loads(payload)
        self.messages.append(message)
        return message

    def diagnostics(self) -> str:
        stderr_chunks: list[bytes] = []
        if self.process.stderr is not None:
            while select.select([self.process.stderr], [], [], 0)[0]:
                chunk = os.read(self.process.stderr.fileno(), 65536)
                if not chunk:
                    break
                stderr_chunks.append(chunk)
        stderr = b"".join(stderr_chunks).decode(errors="replace")
        return f"messages={self.messages!r}\nadapter stderr:\n{stderr}"

    def wait_for(self, predicate: Any, timeout: float = 45) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        seen = []
        while time.monotonic() < deadline:
            message = self.read(deadline - time.monotonic())
            seen.append(message)
            if predicate(message):
                return message
        raise TimeoutError(f"DAP condition not met; messages={seen}")

    def response(self, command: str, timeout: float = 45) -> dict[str, Any]:
        message = self.wait_for(
            lambda item: item.get("type") == "response" and item.get("command") == command,
            timeout,
        )
        if not message.get("success"):
            raise AssertionError(f"DAP {command} failed: {message}")
        return message

    def stopped(self, reason: str, timeout: float = 45) -> dict[str, Any]:
        message = self.wait_for(
            lambda item: item.get("type") == "event"
            and item.get("event") in {"stopped", "terminated"},
            timeout,
        )
        if message.get("event") != "stopped" or message.get("body", {}).get("reason") != reason:
            raise AssertionError(
                f"expected stopped({reason}), got {message}\n{self.diagnostics()}"
            )
        return message


def trace_index(recording: Path) -> dict[str, Any]:
    result = subprocess.run(
        [replay_binary(recording), "--recording", str(recording), "--index"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def direct_replay(recording: Path, expected_text: str) -> None:
    shutil.rmtree(recording.with_suffix(".d"), ignore_errors=True)
    index = trace_index(recording)
    pid = int(index["root"]["pid"])
    subprocess.run(
        [replay_binary(recording), "--recording", str(recording), "--extract"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pidfile = recording.with_suffix(".d") / f"{pid}.bin"
    result = subprocess.run(
        [str(pidfile)],
        cwd=index["root"]["preamble"]["cwd"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 1 or expected_text not in result.stdout:
        raise AssertionError(
            f"direct replay did not reproduce expected failure: status={result.returncode}\n{result.stdout}"
        )


def dap_replay(name: str, demo: dict[str, Any]) -> None:
    recording = demo["recording"]
    source = demo["source"]
    line = int(demo["line"])
    index = trace_index(recording)
    pid = int(index["root"]["pid"])
    client = DAPClient(recording, pid)
    try:
        client.send("initialize", {"clientID": "retrace-demo-verifier", "adapterID": "retrace"})
        client.response("initialize")
        client.send(
            "launch",
            {"type": "retrace", "request": "launch", "recording": str(recording)},
        )
        client.response("launch")
        client.send(
            "setBreakpoints",
            {
                "source": {"name": source.name, "path": str(source)},
                "lines": [line],
                "breakpoints": [{"line": line}],
            },
        )
        breakpoint_response = client.response("setBreakpoints", timeout=90)
        breakpoints = breakpoint_response.get("body", {}).get("breakpoints", [])
        if not breakpoints or not breakpoints[0].get("verified"):
            raise AssertionError(f"unverified breakpoint: {breakpoint_response}")

        client.send("configurationDone")
        client.stopped("breakpoint", timeout=90)

        client.send("stackTrace", {"threadId": 1})
        stack = client.response("stackTrace")
        frames = stack.get("body", {}).get("stackFrames", [])
        frame = next(
            (
                item
                for item in frames
                if item.get("source", {}).get("path") == str(source) and int(item.get("line", 0)) == line
            ),
            None,
        )
        if frame is None:
            raise AssertionError(f"breakpoint frame missing from stack: {frames}")

        client.send("scopes", {"frameId": int(frame["id"])})
        scopes = client.response("scopes").get("body", {}).get("scopes", [])
        local_scope = next((scope for scope in scopes if scope.get("name") == "Locals"), None)
        if not local_scope or not local_scope.get("variablesReference"):
            raise AssertionError(f"locals scope unavailable: {scopes}")

        client.send("variables", {"variablesReference": int(local_scope["variablesReference"])})
        variables = client.response("variables").get("body", {}).get("variables", [])
        names = {item.get("name") for item in variables}
        missing = set(demo["locals"]) - names
        if missing:
            raise AssertionError(f"missing useful locals {sorted(missing)}; found {sorted(names)}")

        by_name = {str(item.get("name")): str(item.get("value")) for item in variables}
        for variable, expected in (demo.get("expected_values") or {}).items():
            observed = by_name.get(variable, "")
            if expected not in observed:
                raise AssertionError(
                    f"fresh recording local mismatch for {variable}: "
                    f"expected {expected!r} in {observed!r}"
                )
    finally:
        client.close()

    suffix = " exact_runtime_values=pass" if demo.get("expected_values") else ""
    print(
        f"demo={name} direct_replay=pass breakpoint=pass stack=pass "
        f"scopes=pass locals=pass{suffix}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--environment", action="store_true")
    group.add_argument("--all", action="store_true")
    group.add_argument("--demo", choices=sorted(DEMOS))
    group.add_argument("--recording", type=Path)
    args = parser.parse_args()

    environment_check()
    if args.environment:
        return

    if args.recording:
        selected = [("runtime-state-live", live_demo(args.recording.resolve()))]
    else:
        names = list(DEMOS) if args.all else [args.demo]
        selected = [(name, DEMOS[name]) for name in names]

    for name, demo in selected:
        recording_check(demo)
        direct_replay(demo["recording"], demo["replay_text"])
        shutil.rmtree(demo["recording"].with_suffix(".d"), ignore_errors=True)
        dap_replay(name, demo)
        shutil.rmtree(demo["recording"].with_suffix(".d"), ignore_errors=True)


if __name__ == "__main__":
    main()
