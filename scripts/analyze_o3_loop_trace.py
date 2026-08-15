#!/usr/bin/env python3
"""Group gem5 O3PipeView trace records by dynamic loop iterations."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def parse_int(value):
    return int(value, 0)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, help="Raw O3PipeView trace")
    parser.add_argument("--loop-start-pc", required=True, type=parse_int)
    parser.add_argument("--loop-end-pc", required=True, type=parse_int)
    parser.add_argument("--cycle-ticks", type=int, default=500)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-jsonl", help="Optional per-iteration trace")
    parser.add_argument("--summary", help="Optional summary text output")
    return parser.parse_args()


def read_o3pipe_trace(path):
    insts = []
    cur = None

    with Path(path).open("r", encoding="utf-8", errors="ignore") as trace:
        for raw in trace:
            line = raw.rstrip("\n")
            fields = line.split(":")
            if len(fields) < 3 or fields[0] != "O3PipeView":
                continue

            stage = fields[1]
            if stage == "fetch":
                if cur is not None:
                    insts.append(cur)
                if len(fields) < 7:
                    cur = None
                    continue
                cur = {
                    "fetch": int(fields[2]),
                    "pc": int(fields[3], 16),
                    "upc": int(fields[4]),
                    "seq_num": int(fields[5]),
                    "disasm": ":".join(fields[6:]).strip(),
                    "decode": 0,
                    "rename": 0,
                    "dispatch": 0,
                    "issue": 0,
                    "complete": 0,
                    "retire": 0,
                    "store_complete": 0,
                }
                continue

            if cur is None:
                continue

            if stage in ("decode", "rename", "dispatch", "issue", "complete"):
                cur[stage] = int(fields[2])
            elif stage == "retire":
                cur["retire"] = int(fields[2])
                if len(fields) >= 5 and fields[3] == "store":
                    cur["store_complete"] = int(fields[4])

    if cur is not None:
        insts.append(cur)

    return insts


def group_loop_iterations(insts, loop_start_pc, loop_end_pc, cycle_ticks):
    committed = [inst for inst in insts if inst["retire"] > 0]
    committed.sort(key=lambda inst: inst["seq_num"])

    iterations = []
    i = 0
    while i < len(committed):
        inst = committed[i]
        if inst["pc"] != loop_start_pc:
            i += 1
            continue

        if i == 0:
            raise RuntimeError("loop-start instruction has no previous inst")

        prev_inst = committed[i - 1]
        j = i
        while j < len(committed) and committed[j]["pc"] != loop_end_pc:
            j += 1
        if j >= len(committed):
            break

        first_inst = committed[i]
        last_inst = committed[j]
        duration_ticks = last_inst["retire"] - prev_inst["retire"]
        body = committed[i : j + 1]
        iterations.append(
            {
                "iter": len(iterations),
                "prev_seq": prev_inst["seq_num"],
                "first_seq": first_inst["seq_num"],
                "last_seq": last_inst["seq_num"],
                "prev_pc": f"0x{prev_inst['pc']:x}",
                "first_pc": f"0x{first_inst['pc']:x}",
                "last_pc": f"0x{last_inst['pc']:x}",
                "prev_retire_tick": prev_inst["retire"],
                "last_retire_tick": last_inst["retire"],
                "cycles": duration_ticks / cycle_ticks,
                "body_inst_count": j - i + 1,
                "first_disasm": first_inst["disasm"],
                "last_disasm": last_inst["disasm"],
                "instructions": body,
            }
        )
        i = j + 1

    return iterations


def write_csv(path, rows):
    fields = [
        "iter",
        "cycles",
        "body_inst_count",
        "prev_retire_tick",
        "last_retire_tick",
        "prev_seq",
        "first_seq",
        "last_seq",
        "prev_pc",
        "first_pc",
        "last_pc",
        "first_disasm",
        "last_disasm",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def tick_to_cycle(tick, cycle_ticks):
    return None if tick == 0 else tick / cycle_ticks


def write_jsonl(path, rows, cycle_ticks):
    with Path(path).open("w", encoding="utf-8") as out:
        for row in rows:
            payload = {k: v for k, v in row.items() if k != "instructions"}
            payload["instructions"] = []
            for inst in row["instructions"]:
                payload["instructions"].append(
                    {
                        "seq_num": inst["seq_num"],
                        "pc": f"0x{inst['pc']:x}",
                        "disasm": inst["disasm"],
                        "fetch_cycle": tick_to_cycle(inst["fetch"], cycle_ticks),
                        "decode_cycle": tick_to_cycle(inst["decode"], cycle_ticks),
                        "rename_cycle": tick_to_cycle(inst["rename"], cycle_ticks),
                        "dispatch_cycle": tick_to_cycle(
                            inst["dispatch"], cycle_ticks
                        ),
                        "issue_cycle": tick_to_cycle(inst["issue"], cycle_ticks),
                        "complete_cycle": tick_to_cycle(
                            inst["complete"], cycle_ticks
                        ),
                        "retire_cycle": tick_to_cycle(inst["retire"], cycle_ticks),
                        "store_complete_cycle": tick_to_cycle(
                            inst["store_complete"], cycle_ticks
                        ),
                    }
                )
            out.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_summary(rows):
    if not rows:
        return "No loop iterations found.\n"

    cycles = [row["cycles"] for row in rows]
    hist = Counter(cycles)
    sorted_cycles = sorted(cycles)
    steady = hist.most_common(1)[0]
    lines = [
        f"iterations: {len(rows)}",
        f"min_cycles: {min(cycles):.2f}",
        f"max_cycles: {max(cycles):.2f}",
        f"mean_cycles: {sum(cycles) / len(cycles):.2f}",
        f"median_cycles: {sorted_cycles[len(sorted_cycles) // 2]:.2f}",
        f"mode_cycles: {steady[0]:.2f} ({steady[1]} iterations)",
        "",
        "histogram_cycles:",
    ]
    for value, count in sorted(hist.items()):
        lines.append(f"  {value:.2f}: {count}")

    slow_rows = [row for row in rows if row["cycles"] > steady[0]]
    if slow_rows:
        lines.extend(["", "slow_iterations_above_mode:"])
        for row in slow_rows[:40]:
            lines.append(f"  iter {row['iter']}: {row['cycles']:.2f} cycles")
        if len(slow_rows) > 40:
            lines.append(f"  ... {len(slow_rows) - 40} more")

    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    insts = read_o3pipe_trace(args.trace)
    rows = group_loop_iterations(
        insts,
        args.loop_start_pc,
        args.loop_end_pc,
        args.cycle_ticks,
    )
    write_csv(args.output_csv, rows)
    if args.output_jsonl:
        write_jsonl(args.output_jsonl, rows, args.cycle_ticks)
    summary = build_summary(rows)
    if args.summary:
        Path(args.summary).write_text(summary, encoding="utf-8")
    print(summary, end="")


if __name__ == "__main__":
    main()
