#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2
"""Run the kernel mutation gate and replay excluded equivalent mutants.

The gate leg runs ``cargo mutants`` with ``.cargo/mutants.toml`` and proves that
every non-excluded kernel mutant that builds is caught by the test suite, and
that the number of mutants that fail to build stays at or below a recorded
ceiling. The planted leg replays only the ``exclude_re`` patterns with
``--no-config`` and proves both that the gate fails when a mutant survives and
that every exclusion still names exactly one surviving equivalent mutant.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

CONFIG_PATH = Path(".cargo/mutants.toml")
ALLOWED_KEYS = frozenset({"exclude_re", "additional_cargo_args", "cap_lints"})
# Arguments after ``cargo mutants`` shared by both legs.
COMMON_ARGS = ("-p", "kernel", "--no-shuffle", "--timeout", "120")
GATE_OUTPUT = Path("mutants.out")
GATE_OLD_OUTPUT = Path("mutants.out.old")
# Leg + stop time must fit mutants job timeout-minutes in .github/workflows/rust.yml.
GATE_TIMEOUT_SECONDS = 900
PLANTED_TIMEOUT_SECONDS = 600
# Grace period after SIGTERM for cargo-mutants to stop its child process groups.
TERMINATE_GRACE_SECONDS = 60
# Reap deadline after SIGKILL so a stuck process cannot block indefinitely.
KILL_WAIT_SECONDS = 10
# Upper bound on the delay between a recorded SIGINT/SIGTERM and the start of
# the leg stop.
LEG_POLL_SECONDS = 1
# First SIGINT or SIGTERM the script received; set only by request_cancel.
CANCEL_SIGNALS: list[int] = []
# Minimum whitespace-separated fields after ``)`` in /proc/<pid>/stat for session.
MIN_PROC_STAT_FIELDS = 4
EMPTY_OUTCOME_FILES = ("caught.txt", "timeout.txt", "unviable.txt")
# cargo-mutants exit code when at least one mutant was missed.
MISSED_EXIT_CODE = 2
# Unviable gate mutants measured 2026-11-24 with cap_lints (68 without); raise it
# only in a reviewed change.
GATE_UNVIABLE_CEILING = 31


@dataclass(frozen=True)
class MutantsConfig:
    """Validated ``.cargo/mutants.toml`` settings mirrored by the planted leg."""

    exclude_re: list[tuple[str, re.Pattern[str]]]
    additional_cargo_args: list[str]
    cap_lints: bool


class LegCancelled(Exception):
    """Raised by ``run_leg`` after it stopped a leg on ``SIGINT`` or ``SIGTERM``."""

    def __init__(self, signum: int) -> None:
        """Store the signal number ``signum`` that cancelled the leg."""
        self.signum = signum
        super().__init__(signum)


def err(message: str) -> None:
    """Write a prefixed diagnostic message to standard error."""
    print(f"mutants-check: {message}", file=sys.stderr)


def request_cancel(signum: int, frame: FrameType | None) -> None:
    """Record the first ``SIGINT`` or ``SIGTERM`` in ``CANCEL_SIGNALS``.

    Never raises, so a later signal cannot cut a leg stop short.
    """
    if not CANCEL_SIGNALS:
        CANCEL_SIGNALS.append(signum)


def parse_string_list(raw: object, key: str, path: Path) -> list[str] | None:
    """Validate that ``raw`` is a list of strings, or report a type error."""
    if not isinstance(raw, list):
        err(f"{key} in {path} must be a list of strings")
        return None
    items = list(raw)
    for idx in range(len(items)):
        if not isinstance(items[idx], str):
            err(f"{key} in {path} must contain only strings")
            return None
    return items


def compile_exclusions(
    patterns: list[str], path: Path
) -> list[tuple[str, re.Pattern[str]]] | None:
    """Compile each exclusion pattern in ``patterns`` as a regular expression."""
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for idx in range(len(patterns)):
        pattern = patterns[idx]
        try:
            compiled.append((pattern, re.compile(pattern)))
        except re.error as exc:
            err(f"invalid exclude_re regex {pattern!r} in {path}: {exc}")
            return None
    return compiled


def parse_exclusions(
    raw: dict[str, object], path: Path
) -> tuple[list[tuple[str, re.Pattern[str]]] | None, int]:
    """Extract and validate non-empty ``exclude_re`` patterns from ``raw``."""
    if "exclude_re" not in raw:
        err(f"planted leg has no excluded mutant to replay ({path} omits exclude_re)")
        return None, 1
    patterns = parse_string_list(raw["exclude_re"], "exclude_re", path)
    if patterns is None:
        return None, 2
    if not patterns:
        err(
            f"planted leg has no excluded mutant to replay ({path} exclude_re is empty)"
        )
        return None, 1
    compiled = compile_exclusions(patterns, path)
    if compiled is None:
        return None, 2
    return compiled, 0


def load_config(path: Path) -> tuple[MutantsConfig | None, int]:
    """Read ``.cargo/mutants.toml`` and validate its keys and value types."""
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        err(f"failed to read {path}: {exc}")
        return None, 2

    keys = sorted(raw.keys())
    unknown: list[str] = []
    for idx in range(len(keys)):
        if keys[idx] not in ALLOWED_KEYS:
            unknown.append(keys[idx])
    if unknown:
        err(f"unsupported key in {path}: {', '.join(unknown)}")
        return None, 2

    cap_lints = raw.get("cap_lints", False)
    if not isinstance(cap_lints, bool):
        err(f"cap_lints in {path} must be a boolean")
        return None, 2

    cargo_args = parse_string_list(
        raw.get("additional_cargo_args", []), "additional_cargo_args", path
    )
    if cargo_args is None:
        return None, 2

    exclusions, status = parse_exclusions(raw, path)
    if exclusions is None:
        return None, status
    return MutantsConfig(exclusions, cargo_args, cap_lints), 0


def build_planted_args(config: MutantsConfig, output_dir: Path) -> list[str]:
    """Build the ``--no-config`` arguments mirroring ``config``."""
    args = [*COMMON_ARGS, "--no-config", "--output", str(output_dir)]
    if config.cap_lints:
        args.extend(["--cap-lints", "true"])
    for idx in range(len(config.additional_cargo_args)):
        args.append(f"--cargo-arg={config.additional_cargo_args[idx]}")
    for idx in range(len(config.exclude_re)):
        pattern, _ = config.exclude_re[idx]
        args.extend(["-F", pattern])
    return args


def read_proc_pgid_session(entry: str) -> tuple[int, int] | None:
    """Read ``(pgid, session)`` for numeric ``/proc`` ``entry``, or ``None``."""
    # Linux only: /proc/<pid>/stat exists only on procfs platforms (proc(5)
    # field 5 pgrp, field 6 session).
    if not (entry.isascii() and entry.isdigit()):
        return None
    try:
        stat = Path(f"/proc/{entry}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    rparen = stat.rfind(")")
    if rparen < 0:
        return None
    fields = stat[rparen + 1 :].split()
    if len(fields) < MIN_PROC_STAT_FIELDS:
        return None
    try:
        return int(fields[2]), int(fields[3])
    except ValueError:
        return None


def session_process_groups(sid: int) -> list[int] | None:
    """Return distinct process group IDs in session ``sid`` from ``/proc``.

    Linux only: returns ``None`` when ``/proc`` is not a directory because other
    platforms have no ``/proc``.
    """
    # Linux only: other platforms have no /proc directory.
    if not Path("/proc").is_dir():
        return None
    try:
        entries = os.listdir("/proc")
    except OSError as exc:
        err(f"failed to list /proc: {exc}")
        return None
    own_pgid = os.getpgrp()
    groups: list[int] = []
    for idx in range(len(entries)):
        parsed = read_proc_pgid_session(entries[idx])
        if parsed is None:
            continue
        pgid, session = parsed
        if session == sid and pgid > 1 and pgid != own_pgid and pgid not in groups:
            groups.append(pgid)
    return groups


def kill_process_group(leg_name: str, pgid: int) -> None:
    """Send ``SIGKILL`` to process group ``pgid`` when ``pgid`` is above ``1``."""
    if pgid <= 1:
        return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError as exc:
        err(f"{leg_name} leg failed to kill process group {pgid}: {exc}")


def stop_leg(leg_name: str, proc: subprocess.Popen[bytes]) -> None:
    """Stop a ``cargo mutants`` process with SIGTERM, then SIGKILL.

    ``cargo-mutants`` runs in its own session and starts each cargo build and
    test child in its own process group, waiting for those groups without a
    deadline on ``SIGTERM``. When ``SIGTERM`` times out, ``cargo-mutants`` is
    killed with ``SIGKILL`` first and remaining process groups in its session,
    including reparented descendants, are discovered from ``/proc`` and killed
    by group; without ``/proc`` they may keep running. Signals arriving during
    the stop are only recorded, so the stop always completes.
    """
    proc.terminate()
    try:
        proc.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    else:
        return
    proc.kill()
    groups = session_process_groups(proc.pid)
    if groups is None:
        err(
            f"{leg_name} leg ignored SIGTERM for {TERMINATE_GRACE_SECONDS}s; "
            "killing cargo-mutants, its build and test process groups may keep "
            "running"
        )
    else:
        err(
            f"{leg_name} leg ignored SIGTERM for {TERMINATE_GRACE_SECONDS}s; "
            f"killing cargo-mutants and {len(groups)} process groups in its "
            "session"
        )
        for idx in range(len(groups)):
            kill_process_group(leg_name, groups[idx])
    try:
        proc.wait(timeout=KILL_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        err(f"{leg_name} leg did not exit after kill")


def run_leg(leg_name: str, args: list[str], timeout_seconds: int) -> int | None:
    """Run ``cargo mutants`` with ``args`` and a bounded SIGTERM-then-kill deadline.

    The executable and subcommand are literals at the call site, each element
    of ``args`` is passed as one argv element without a shell, and the leg runs
    in a session of its own so every descendant can be found. Exceeding
    ``timeout_seconds`` stops the leg with ``SIGTERM`` then ``SIGKILL``. A
    ``SIGINT`` or ``SIGTERM`` to the script is recorded by ``request_cancel``
    and stops the leg the same way within ``LEG_POLL_SECONDS``, then
    ``LegCancelled`` is raised; the return value is unchanged otherwise.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    if CANCEL_SIGNALS:
        raise LegCancelled(CANCEL_SIGNALS[0])
    try:
        proc = subprocess.Popen(["cargo", "mutants", *args], start_new_session=True)
    except OSError as exc:
        err(f"{leg_name} leg failed to start cargo-mutants: {exc}")
        return None
    deadline = time.monotonic() + timeout_seconds
    for _ in range(timeout_seconds // LEG_POLL_SECONDS + 2):
        if CANCEL_SIGNALS:
            err(
                f"{leg_name} leg cancelled by "
                f"{signal.Signals(CANCEL_SIGNALS[0]).name}; stopping cargo-mutants"
            )
            stop_leg(leg_name, proc)
            raise LegCancelled(CANCEL_SIGNALS[0])
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            return proc.wait(timeout=min(LEG_POLL_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            continue
    err(f"{leg_name} leg exceeded its {timeout_seconds}s deadline")
    stop_leg(leg_name, proc)
    return None


def read_outcome_file(mutants_out: Path, name: str) -> list[str] | None:
    """Read lines from ``mutants_out / name``, returning ``[]`` when empty."""
    path = mutants_out / name
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        err(f"failed to read {name}: {exc}")
        return None
    if not content:
        return []
    return content.splitlines()


def check_empty_outcomes(mutants_out: Path) -> bool | None:
    """Verify that ``caught.txt``, ``timeout.txt`` and ``unviable.txt`` are empty."""
    clean = True
    for idx in range(len(EMPTY_OUTCOME_FILES)):
        name = EMPTY_OUTCOME_FILES[idx]
        lines = read_outcome_file(mutants_out, name)
        if lines is None:
            return None
        if lines:
            err(f"planted leg produced non-empty {name}: {lines[0]}")
            clean = False
    return clean


def match_pattern_indices(regex: re.Pattern[str], lines: list[str]) -> list[int]:
    """Return indices of ``lines`` matched by ``regex`` via ``re.search``."""
    hits: list[int] = []
    for idx in range(len(lines)):
        if regex.search(lines[idx]) is not None:
            hits.append(idx)
    return hits


def verify_planted_outputs(
    mutants_out: Path,
    exclusions: list[tuple[str, re.Pattern[str]]],
) -> list[str] | None:
    """Verify ``missed.txt`` bijection and emptiness of the other three files."""
    missed_lines = read_outcome_file(mutants_out, "missed.txt")
    if missed_lines is None:
        return None
    empty_ok = check_empty_outcomes(mutants_out)
    if empty_ok is None:
        return None

    ok = empty_ok
    if len(missed_lines) != len(exclusions):
        err(f"missed.txt line count is {len(missed_lines)}, expected {len(exclusions)}")
        ok = False

    seen: set[int] = set()
    for idx in range(len(exclusions)):
        pattern, regex = exclusions[idx]
        hits = match_pattern_indices(regex, missed_lines)
        if len(hits) != 1:
            err(
                f"exclude_re pattern {pattern!r} matched {len(hits)} "
                f"missed.txt lines, expected 1"
            )
            ok = False
        elif hits[0] in seen:
            err(
                f"exclude_re pattern {pattern!r} matched duplicate "
                f"missed.txt line: {missed_lines[hits[0]]}"
            )
            ok = False
        else:
            seen.add(hits[0])
    return missed_lines if ok else None


def run_planted_leg(config: MutantsConfig) -> int:
    """Execute the planted leg in a temporary directory and verify outcomes."""
    with tempfile.TemporaryDirectory(prefix="mutants-check-") as tmp_dir:
        output_dir = Path(tmp_dir)
        args = build_planted_args(config, output_dir)
        rc = run_leg("planted", args, PLANTED_TIMEOUT_SECONDS)
        if rc is None:
            return 1
        mutants_out = output_dir / "mutants.out"
        if rc != MISSED_EXIT_CODE:
            err(
                f"planted leg exited with {rc}, "
                f"expected {MISSED_EXIT_CODE} (missed mutants)"
            )
            if mutants_out.is_dir():
                verify_planted_outputs(mutants_out, config.exclude_re)
            return 1
        missed_lines = verify_planted_outputs(mutants_out, config.exclude_re)
        if missed_lines is None:
            return 1
        for idx in range(len(missed_lines)):
            print(missed_lines[idx])
        print(
            f"mutants-check: gate passed; planted leg replayed "
            f"{len(missed_lines)} excluded mutants"
        )
        return 0


def run_gate_leg() -> int:
    """Execute the gate leg, remove ``.old`` output, and check unviable count."""
    gate_rc = run_leg("gate", list(COMMON_ARGS), GATE_TIMEOUT_SECONDS)
    if GATE_OLD_OUTPUT.exists():
        try:
            shutil.rmtree(GATE_OLD_OUTPUT)
        except OSError as exc:
            err(f"failed to remove {GATE_OLD_OUTPUT}: {exc}")
            return 1
    if gate_rc is None:
        return 1
    if gate_rc != 0:
        err(f"gate leg failed (cargo-mutants exit {gate_rc})")
        return 1
    lines = read_outcome_file(GATE_OUTPUT, "unviable.txt")
    if lines is None:
        return 1
    n = 0
    for idx in range(len(lines)):
        if lines[idx]:
            n += 1
    if n > GATE_UNVIABLE_CEILING:
        err(
            f"gate leg: {n} unviable mutants exceed the ceiling of "
            f"{GATE_UNVIABLE_CEILING}; a config or code change stopped them "
            "from building"
        )
        return 1
    if n < GATE_UNVIABLE_CEILING:
        print(
            f"mutants-check: gate unviable {n} below ceiling "
            f"{GATE_UNVIABLE_CEILING}; lower GATE_UNVIABLE_CEILING"
        )
    return 0


def main() -> int:
    """Run configuration validation, the gate leg, and the planted leg."""
    # Signals are recorded, never raised, so a leg stop cannot be interrupted
    # (cargo-mutants runs in its own session and does not get them).
    signal.signal(signal.SIGINT, request_cancel)
    signal.signal(signal.SIGTERM, request_cancel)
    config, status = load_config(CONFIG_PATH)
    if config is None:
        return status
    try:
        gate_status = run_gate_leg()
        if gate_status != 0:
            return gate_status
        return run_planted_leg(config)
    except LegCancelled as exc:
        err(f"cancelled by {signal.Signals(exc.signum).name}")
        return 128 + exc.signum


if __name__ == "__main__":
    sys.exit(main())
