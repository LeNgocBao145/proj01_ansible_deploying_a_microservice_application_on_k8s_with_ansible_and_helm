#!/usr/bin/env python3
"""Derive Helm resource profiles from repeated `kubectl top` samples."""

from __future__ import annotations

import argparse
import math
import re
from datetime import datetime, timezone
from pathlib import Path


def cpu_millicores(value: str) -> float:
    if value.endswith("m"):
        return float(value[:-1])
    return float(value) * 1000


def memory_bytes(value: str) -> float:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMGTE]i?|)", value)
    if not match:
        raise ValueError(f"unsupported memory quantity: {value}")
    number = float(match.group(1))
    suffix = match.group(2)
    powers = {"": 1, "K": 1000, "M": 1000**2, "G": 1000**3,
              "T": 1000**4, "E": 1000**5, "Ki": 1024,
              "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
              "Ei": 1024**5}
    return number * powers[suffix]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workloads", required=True)
    args = parser.parse_args()
    workloads = [name for name in args.workloads.split(",") if name]
    if not workloads:
        parser.error("at least one workload name is required")

    peaks: dict[str, dict[str, float]] = {}
    sample_markers = 0
    for raw_line in args.input.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("# Sample "):
            sample_markers += 1
            continue
        fields = line.split()
        if len(fields) < 4:
            continue
        pod_name, _container, cpu, memory = fields[:4]
        workload = next(
            (name for name in sorted(workloads, key=len, reverse=True)
             if pod_name.startswith(name + "-")),
            None,
        )
        if workload is None:
            continue
        sample = peaks.setdefault(workload, {"cpu_m": 0.0, "memory_b": 0.0})
        try:
            sample["cpu_m"] = max(sample["cpu_m"], cpu_millicores(cpu))
            sample["memory_b"] = max(sample["memory_b"], memory_bytes(memory))
        except ValueError as exc:
            parser.error(str(exc))

    missing = sorted(set(workloads) - set(peaks))
    if missing:
        parser.error("no metrics were captured for: " + ", ".join(missing))
    if sample_markers < 2:
        parser.error("at least two marked metric samples are required")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "# Generated from the matching timestamped kubectl top samples.",
        "# Requests follow observed peaks with startup floors; limits include headroom and startup floors.",
        "resource_measurement:",
        f'  sampled_at_utc: "{datetime.now(timezone.utc).isoformat(timespec="seconds")}"',
        f"  sample_count: {sample_markers}",
        "  source: reports/part5-resource-samples.txt",
        "resource_observed_peaks:",
    ]
    for workload in workloads:
        peak = peaks[workload]
        observed_cpu = max(1, math.ceil(peak["cpu_m"]))
        observed_memory_mi = max(1, math.ceil(peak["memory_b"] / (1024**2)))
        lines.extend([
            f"  {workload}:",
            f'    cpu: "{observed_cpu}m"',
            f'    memory: "{observed_memory_mi}Mi"',
        ])
    lines.append("microservice_resource_profiles:")
    for workload in workloads:
        peak = peaks[workload]
        cpu_req = max(1, math.ceil(peak["cpu_m"] / 10) * 10)
        # Idle/short kubectl-top samples understate startup resource needs.
        # Tiny CFS quotas delay gRPC probes; tiny memory limits OOM kill services.
        cpu_limit = max(cpu_req, 250, math.ceil((peak["cpu_m"] * 2) / 10) * 10)
        mem_req_mi = max(64, math.ceil(peak["memory_b"] / (1024**2)))
        mem_limit_mi = max(mem_req_mi, 256, math.ceil((peak["memory_b"] * 1.5) / (1024**2)))
        lines.extend([
            f"  {workload}:",
            "    requests:",
            f'      cpu: "{cpu_req}m"',
            f'      memory: "{mem_req_mi}Mi"',
            "    limits:",
            f'      cpu: "{cpu_limit}m"',
            f'      memory: "{mem_limit_mi}Mi"',
        ])
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote measured profiles for {len(peaks)} workloads to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
