#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2
"""Run the kernel and kernel-std mutation gate and replay excluded equivalent mutants.

The gate leg runs ``cargo mutants`` with ``.cargo/mutants.toml``, which must carry
the test runner memory cap. The gate verifies that every non-excluded mutant in
both packages that builds is caught by the test suite, and that the number of
mutants that fail to build stays at or below a recorded ceiling. The planted leg
replays only the ``exclude_re`` patterns with ``--no-config`` and proves both that
the gate fails when a mutant survives and that every exclusion still names
exactly one surviving equivalent mutant. The Linux-only runner marks itself a
child subreaper, strips ``CARGO_MUTANTS_*`` and ``CARGO_TARGET_*_RUNNER``
environment overrides, kills session and reparented leftovers through pidfds,
and fails closed unless ``waitpid(-1, WNOHANG)`` proves ``ECHILD``.
"""

from __future__ import annotations

import ctypes
import os
import re
import select
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

CONFIG_PATH = Path(".cargo/mutants.toml")
ALLOWED_KEYS = frozenset({"exclude_re", "additional_cargo_args", "cap_lints"})
# Required as one additional_cargo_args entry in .cargo/mutants.toml.
TEST_RUNNER_CAP_ARG = """--config=target.'cfg(target_os = "linux")'.runner=["prlimit", "--as=4294967296"]"""
# Each element is forwarded to Cargo. Another --config argument could set a target
# runner that overrides the cap, so adding an element here requires review.
ALLOWED_CARGO_ARGS = ("--locked", TEST_RUNNER_CAP_ARG)
# Arguments after ``cargo mutants`` shared by both legs. ``--jobs 1`` runs one
# mutant build+test at a time as an explicit HISS-06 worker bound; the default
# was measured at 1 worker (one ``start thread`` in ``mutants.out/debug.log`` on
# ``cargo-mutants`` 27.1.0 on a 32-CPU host), so counts and timing are
# unchanged, while the ``cargo-mutants`` jobserver caps compile tasks at the CPU
# count.
COMMON_ARGS = (
    "-p",
    "kernel",
    "-p",
    "kernel-std",
    "--jobs",
    "1",
    "--no-shuffle",
    "--timeout",
    "120",
)
CARGO_MUTANTS_ENV_PREFIX = "CARGO_MUTANTS_"
# Leg + stop time must fit mutants job timeout-minutes in .github/workflows/rust.yml:
# stop takes at most TERMINATE_GRACE_SECONDS + 2 * KILL_WAIT_SECONDS = 80 s (grace
# plus up to two kill waits), and cleanup adds at most
# 2 * CLEANUP_ROUNDS * CLEANUP_ROUND_WAIT_SECONDS = 2 s per leg end (session pass,
# then orphan reap), for 82 s per leg end and 900 + 600 + 2 * 82 = 1664 s total.
GATE_TIMEOUT_SECONDS = 900
PLANTED_TIMEOUT_SECONDS = 600
# Grace period after SIGTERM for cargo-mutants to stop its child process groups.
TERMINATE_GRACE_SECONDS = 60
# Reap deadline after SIGKILL so a stuck process cannot block indefinitely.
KILL_WAIT_SECONDS = 10
# Upper bound on the delay between a recorded SIGINT/SIGTERM and the start of
# the leg stop.
LEG_POLL_SECONDS = 1
# Poll interval while waiting for cargo-mutants to exit without reaping it.
EXIT_POLL_SECONDS = 0.05
# Maximum /proc kill rounds run at the end of a leg; a final scan follows the last.
CLEANUP_ROUNDS = 5
# Wait between /proc scan-and-kill rounds so killed processes can exit.
CLEANUP_ROUND_WAIT_SECONDS = 0.2
# Linux prctl(2) option value from /usr/include/linux/prctl.h.
PR_SET_CHILD_SUBREAPER = 36
# Upper bound on exited children reaped per round before re-scanning /proc.
REAP_DRAIN_LIMIT = 256
DRAIN_EMPTY = "empty"
DRAIN_LIVE = "live"
DRAIN_FAILED = "failed"
# First SIGINT or SIGTERM the script received; set only by request_cancel.
CANCEL_SIGNALS: list[int] = []
# Minimum whitespace-separated fields after ``)`` in /proc/<pid>/stat for
# state, ppid, and session.
MIN_PROC_STAT_FIELDS = 4
PROC_STAT_PARSED = "parsed"
PROC_STAT_VANISHED = "vanished"
PROC_STAT_FAILED = "failed"
SIGNAL_EXIT_BASE = 128
EMPTY_OUTCOME_FILES = ("caught.txt", "timeout.txt", "unviable.txt")
# cargo-mutants exit code when at least one mutant was missed.
MISSED_EXIT_CODE = 2
# Kernel on CI 2026-11-24 at 3737b36: 143 tested, 112 caught, 31 unviable with
# cap_lints (68 unviable without). Kernel-std measured 2026-11-25 on 7e09af5:
# 24 tested, 14 caught, 9 unviable. The new lease point count test catches the
# remaining mutant.
# Unviable gate mutants: 31 + 9. Raise it only in a reviewed change.
GATE_UNVIABLE_CEILING = 40
# Caught gate mutants: 112 + 15. Lower it only in a reviewed change.
GATE_CAUGHT_FLOOR = 127
# Gate mutants tested (caught + unviable): 143 + 24.
# Lower it only in a reviewed change.
GATE_MUTANTS_FLOOR = 167


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


@dataclass(frozen=True)
class ProcStatRead:
    """Outcome of reading ``/proc/<pid>/stat`` for one process entry."""

    status: str
    parsed: tuple[str, int, int] | None = None
    error: str | None = None


def err(message: str) -> None:
    """Write a prefixed diagnostic message to standard error."""
    print(f"mutants-check: {message}", file=sys.stderr)


def request_cancel(signum: int, frame: FrameType | None) -> None:
    """Record the first ``SIGINT`` or ``SIGTERM`` in ``CANCEL_SIGNALS``.

    Never raises, so a later signal cannot cut a leg stop short.
    """
    if not CANCEL_SIGNALS:
        CANCEL_SIGNALS.append(signum)


def cancel_status() -> int | None:
    """Report the first recorded cancellation signal and return its exit code."""
    if not CANCEL_SIGNALS:
        return None
    signum = CANCEL_SIGNALS[0]
    err(f"cancelled by {signal.Signals(signum).name}")
    return SIGNAL_EXIT_BASE + signum


def enable_subreaper() -> bool:
    """Mark the current process as a Linux child subreaper via ``prctl``."""
    # Linux only: orphaned descendants reparent to this process so waitpid(-1)
    # can wait on them (PR_SET_CHILD_SUBREAPER(2const)).
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        prctl = libc.prctl
    except (OSError, AttributeError) as exc:
        err(f"failed to load libc prctl for child subreaper: {exc}")
        return False
    prctl.restype = ctypes.c_int
    rc = prctl(
        ctypes.c_int(PR_SET_CHILD_SUBREAPER),
        ctypes.c_ulong(1),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    if rc != 0:
        err(f"failed to enable child subreaper: {os.strerror(ctypes.get_errno())}")
        return False
    return True


def leg_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """Return a copy without cargo-mutants overrides or per-target Cargo runners."""
    keys = list(environ.keys())
    cleaned: dict[str, str] = {}
    runner_keys: list[str] = []
    for idx in range(len(keys)):
        key = keys[idx]
        if key.startswith("CARGO_TARGET_") and key.endswith("_RUNNER"):
            runner_keys.append(repr(key))
        elif not key.startswith(CARGO_MUTANTS_ENV_PREFIX):
            cleaned[key] = environ[key]
    if runner_keys:
        err(f"dropped Cargo runner environment keys: {', '.join(sorted(runner_keys))}")
    return cleaned


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


def check_cargo_config(path: Path) -> bool:
    """Accept a missing or readable Cargo config without target runners."""
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError:
        return True
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        err(f"failed to read {path}: {exc}")
        return False

    targets = raw.get("target")
    if not isinstance(targets, dict):
        return True
    keys = list(targets)
    for idx in range(len(keys)):
        key = keys[idx]
        target = targets[key]
        # A runner here can override or conflict with the test runner memory cap.
        if isinstance(target, dict) and "runner" in target:
            err(f"runner for target {key!r} in {path} can override the memory cap")
            return False
    return True


def load_config(path: Path) -> tuple[MutantsConfig | None, int]:
    """Validate mutation settings and guard the test runner cap."""
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
    has_runner_cap = TEST_RUNNER_CAP_ARG in cargo_args
    if not has_runner_cap:
        err(
            f"additional_cargo_args in {path} lacks the test runner memory cap "
            f"{TEST_RUNNER_CAP_ARG}"
        )
    unsupported: list[str] = []
    for idx in range(len(cargo_args)):
        if cargo_args[idx] not in ALLOWED_CARGO_ARGS:
            unsupported.append(repr(cargo_args[idx]))
    if unsupported:
        err(f"unsupported additional_cargo_args in {path}: {', '.join(unsupported)}")
    if not has_runner_cap or unsupported:
        return None, 2

    exclusions, status = parse_exclusions(raw, path)
    if exclusions is None:
        return None, status
    cargo_config_names = ("config.toml", "config")
    for idx in range(len(cargo_config_names)):
        if not check_cargo_config(path.parent / cargo_config_names[idx]):
            return None, 2
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


def wait_exited(pid: int, timeout_seconds: float) -> bool:
    """Wait up to ``timeout_seconds`` for child ``pid`` to exit without reaping it."""
    if timeout_seconds < 0:
        timeout_seconds = 0.0
    deadline = time.monotonic() + timeout_seconds
    for _ in range(int(timeout_seconds / EXIT_POLL_SECONDS) + 1):
        try:
            result = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        except ChildProcessError:
            return True
        if result is not None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(EXIT_POLL_SECONDS, remaining))
    try:
        return (
            os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is not None
        )
    except ChildProcessError:
        return True


def signal_leg(proc: subprocess.Popen[bytes], sig: int) -> None:
    """Send ``sig`` to ``proc`` when ``proc.pid`` is above ``1``.

    The PID is our unreaped child, so it cannot belong to another process;
    ``Popen.send_signal`` would reap it through ``poll()``.
    """
    if proc.pid > 1:
        try:
            os.kill(proc.pid, sig)
        except ProcessLookupError:
            return


def parse_proc_stat(text: str) -> tuple[str, int, int] | None:
    """Parse ``(state, ppid, session)`` from ``/proc/<pid>/stat`` content ``text``."""
    rparen = text.rfind(")")
    if rparen < 0:
        return None
    fields = text[rparen + 1 :].split()
    if len(fields) < MIN_PROC_STAT_FIELDS:
        return None
    try:
        return fields[0], int(fields[1]), int(fields[3])
    except ValueError:
        return None


def read_proc_state_session(entry: str) -> ProcStatRead:
    """Read ``(state, ppid, session)`` for numeric ``/proc`` ``entry``.

    Returns ``PROC_STAT_PARSED`` with ``(state, ppid, session)``,
    ``PROC_STAT_VANISHED`` when ``entry`` is non-numeric or exited before the
    read, and ``PROC_STAT_FAILED`` with a reason when ``stat`` could not be read
    or parsed.
    """
    # Linux only: /proc/<pid>/stat exists only on procfs platforms (proc(5)
    # field 3 state, field 4 ppid, field 6 session).
    if not (entry.isascii() and entry.isdigit()):
        return ProcStatRead(PROC_STAT_VANISHED)
    stat_path = Path(f"/proc/{entry}/stat")
    try:
        stat = stat_path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, ProcessLookupError):
        return ProcStatRead(PROC_STAT_VANISHED)
    except OSError as exc:
        return ProcStatRead(PROC_STAT_FAILED, error=f"cannot read {stat_path}: {exc}")
    parsed = parse_proc_stat(stat)
    if parsed is None:
        return ProcStatRead(PROC_STAT_FAILED, error=f"malformed {stat_path}")
    return ProcStatRead(PROC_STAT_PARSED, parsed=parsed)


def zombie_group_exited(pid: int) -> bool | None:
    """Check via pidfd poll whether every thread in zombie ``pid`` has exited.

    Returns ``True`` when the thread group exited or vanished, ``False`` when
    live threads remain, and ``None`` when pidfd inspection fails.
    """
    # Without PIDFD_THREAD, the file descriptor becomes readable only when the
    # last thread in the thread group exits (pidfd_open(2), NOTES).
    try:
        fd = os.pidfd_open(pid)
    except (FileNotFoundError, ProcessLookupError):
        return True
    except OSError as exc:
        err(f"failed to open pidfd for {pid}: {exc}")
        return None
    exited: bool | None = None
    try:
        poller = select.poll()
        poller.register(fd, select.POLLIN)
        events = poller.poll(0)
        exited = False
        for idx in range(len(events)):
            if events[idx][1] & select.POLLIN:
                exited = True
    except OSError as exc:
        err(f"failed to poll pidfd for {pid}: {exc}")
        exited = None
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            err(f"failed to close pidfd for {pid}: {exc}")
            exited = None
    return exited


def session_entry_live(
    pid: int,
    parsed: tuple[str, int, int],
    sid: int,
    own_pid: int,
) -> bool | None:
    """Return whether ``pid`` is a live targetable member of session ``sid``."""
    state, _, session = parsed
    if session != sid or pid in (sid, own_pid) or state == "X":
        return False
    if state == "Z":
        exited = zombie_group_exited(pid)
        if exited is None:
            return None
        return not exited
    return True


def scan_proc_pids(
    include: Callable[[int, tuple[str, int, int]], bool | None],
) -> list[int] | None:
    """Return numeric ``/proc`` PIDs selected by ``include``, or ``None`` on error."""
    # Linux only: other platforms have no /proc directory.
    try:
        if not Path("/proc").is_dir():
            return None
        entries = os.listdir("/proc")
    except OSError as exc:
        err(f"failed to list /proc: {exc}")
        return None
    pids: list[int] = []
    for idx in range(len(entries)):
        entry = entries[idx]
        if not (entry.isascii() and entry.isdigit()):
            continue
        result = read_proc_state_session(entry)
        if result.status == PROC_STAT_FAILED:
            err(f"failed to inspect process {entry}: {result.error}")
            return None
        if result.parsed is None:
            continue
        pid = int(entry)
        keep = include(pid, result.parsed)
        if keep is None:
            return None
        if keep:
            pids.append(pid)
    return pids


def session_live_pids(sid: int) -> list[int] | None:
    """Return live descendant PIDs in session ``sid`` from ``/proc``.

    Linux only: returns ``None`` when ``/proc`` is not a directory, cannot be
    listed, or has an unreadable or unparseable numeric ``stat`` entry. Excludes
    exited zombie thread groups, dead processes, the held session leader
    ``sid``, and the current process.
    """
    own_pid = os.getpid()
    return scan_proc_pids(
        lambda pid, parsed: session_entry_live(pid, parsed, sid, own_pid)
    )


def reparented_children_pids(subreaper_pid: int) -> list[int] | None:
    """Return non-dead PIDs in ``/proc`` whose ``ppid`` is ``subreaper_pid``."""
    return scan_proc_pids(
        lambda pid, parsed: (
            parsed[1] == subreaper_pid and parsed[0] != "X" and pid != subreaper_pid
        )
    )


def send_pidfd_kill(leg_name: str, fd: int, pid: int) -> bool:
    """Send ``SIGKILL`` via ``fd``, ignoring a process that already exited."""
    try:
        signal.pidfd_send_signal(fd, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError as exc:
        err(f"{leg_name} leg failed to kill {pid}: {exc}")
        return False
    return True


def kill_pidfd_matching(
    leg_name: str,
    pid: int,
    matches: Callable[[tuple[str, int, int]], bool],
) -> bool:
    """Kill ``pid`` via a pidfd when its re-read ``stat`` satisfies ``matches``.

    The pidfd pins the process found at open time, so a signal sent through it
    can never reach a process that took ``pid`` later.
    """
    if pid <= 1:
        return True
    try:
        fd = os.pidfd_open(pid)
    except (FileNotFoundError, ProcessLookupError):
        return True
    except OSError as exc:
        err(f"{leg_name} leg failed to open pidfd for {pid}: {exc}")
        return False
    verified = True
    try:
        result = read_proc_state_session(str(pid))
        if result.status == PROC_STAT_FAILED:
            err(f"{leg_name} leg failed to verify {pid}: {result.error}")
            verified = False
        elif result.parsed is not None and matches(result.parsed):
            verified = send_pidfd_kill(leg_name, fd, pid)
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            err(f"{leg_name} leg failed to close pidfd for {pid}: {exc}")
            verified = False
    return verified


def kill_verified(leg_name: str, pid: int, sid: int) -> bool:
    """Kill ``pid`` via a pidfd after re-checking that it belongs to session ``sid``."""
    return kill_pidfd_matching(leg_name, pid, lambda parsed: parsed[2] == sid)


def kill_reparented_child(leg_name: str, pid: int, subreaper_pid: int) -> bool:
    """Kill ``pid`` via a pidfd after re-checking that ``ppid`` is ``subreaper_pid``."""
    return kill_pidfd_matching(leg_name, pid, lambda parsed: parsed[1] == subreaper_pid)


def kill_session_leftovers(leg_name: str, sid: int, reason: str) -> bool:
    """Kill every live process remaining in ``cargo-mutants`` session ``sid``.

    Runs while the ``cargo-mutants`` zombie holds the session ID; every PID is
    re-checked through a pidfd before the signal, and ``False`` is returned when
    cleanup cannot be verified.
    """
    for round_idx in range(CLEANUP_ROUNDS + 1):
        pids = session_live_pids(sid)
        if pids is None:
            err(
                f"{leg_name} leg {reason}: cannot read /proc, processes in its "
                "session may keep running"
            )
            return False
        if not pids:
            return True
        if round_idx == CLEANUP_ROUNDS:
            break
        if round_idx == 0:
            err(
                f"{leg_name} leg {reason} and left {len(pids)} processes in its "
                "session; killing them"
            )
        all_killed = True
        for idx in range(len(pids)):
            if not kill_verified(leg_name, pids[idx], sid):
                all_killed = False
        if not all_killed:
            return False
        time.sleep(CLEANUP_ROUND_WAIT_SECONDS)
    err(
        f"{leg_name} leg {reason}: processes still running in its session "
        f"after {CLEANUP_ROUNDS} kill rounds"
    )
    return False


def drain_waitpid(leg_name: str) -> str:
    """Reap exited children via ``waitpid(-1, WNOHANG)`` up to ``REAP_DRAIN_LIMIT``."""
    for _ in range(REAP_DRAIN_LIMIT):
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return DRAIN_EMPTY
        except OSError as exc:
            err(f"{leg_name} leg failed to wait for descendants: {exc}")
            return DRAIN_FAILED
        if pid == 0:
            return DRAIN_LIVE
    return DRAIN_LIVE


def reap_orphans(leg_name: str) -> bool:
    """Kill and reap reparented descendants until ``waitpid`` raises ``ECHILD``.

    Must be called only after the leg's own ``Popen`` child was reaped by
    ``proc.wait`` so ``waitpid(-1, WNOHANG)`` cannot steal its exit status.
    """
    own_pid = os.getpid()
    for round_idx in range(CLEANUP_ROUNDS + 1):
        drained = drain_waitpid(leg_name)
        if drained == DRAIN_EMPTY:
            return True
        if drained == DRAIN_FAILED:
            return False
        if round_idx == CLEANUP_ROUNDS:
            break
        pids = reparented_children_pids(own_pid)
        if pids is None:
            err(f"{leg_name} leg cannot read /proc to kill reparented descendants")
            return False
        all_killed = True
        for idx in range(len(pids)):
            if not kill_reparented_child(leg_name, pids[idx], own_pid):
                all_killed = False
        if not all_killed:
            return False
        time.sleep(CLEANUP_ROUND_WAIT_SECONDS)
    err(f"{leg_name} leg: descendants still running after {CLEANUP_ROUNDS} rounds")
    return False


def stop_leg(leg_name: str, proc: subprocess.Popen[bytes]) -> None:
    """Stop a ``cargo mutants`` process with SIGTERM, then SIGKILL.

    ``cargo-mutants`` runs in its own session and stays unreaped until session
    cleanup finishes, so its PID keeps the session ID reserved while ``/proc``
    is scanned and remaining descendants are killed via pidfds. After
    ``proc.wait`` reaps ``cargo-mutants``, child-subreaper cleanup kills and
    drains reparented orphans until ``waitpid(-1, WNOHANG)`` raises ``ECHILD``.
    Signals arriving during the stop are only recorded, so the stop always
    completes.
    """
    signal_leg(proc, signal.SIGTERM)
    if wait_exited(proc.pid, TERMINATE_GRACE_SECONDS):
        exited = True
        reason = "stopped by SIGTERM"
    else:
        err(
            f"{leg_name} leg ignored SIGTERM for {TERMINATE_GRACE_SECONDS}s; "
            "killing cargo-mutants and its session"
        )
        signal_leg(proc, signal.SIGKILL)
        exited = wait_exited(proc.pid, KILL_WAIT_SECONDS)
        reason = "killed"
    kill_session_leftovers(leg_name, proc.pid, reason)
    if not exited:
        err(f"{leg_name} leg did not exit after kill")
    try:
        proc.wait(timeout=KILL_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        err(f"{leg_name} leg was not reaped after kill")
        return
    if not reap_orphans(leg_name):
        err(f"{leg_name} leg stop could not verify that all descendants exited")


def reap_exited_leg(leg_name: str, proc: subprocess.Popen[bytes]) -> int | None:
    """Clean up session leftovers, reap ``proc``, and prove no descendants remain.

    After ``proc.wait`` reaps ``cargo-mutants``, child-subreaper cleanup drains
    reparented descendants until ``waitpid(-1, WNOHANG)`` raises ``ECHILD`` as
    proof that no descendant remains.
    """
    cleaned = kill_session_leftovers(leg_name, proc.pid, "exited")
    reaped_rc: int | None = None
    try:
        reaped_rc = proc.wait(timeout=KILL_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        err(f"{leg_name} leg did not reap after exit")
    orphans_reaped = False
    if reaped_rc is not None:
        orphans_reaped = reap_orphans(leg_name)
    if CANCEL_SIGNALS:
        raise LegCancelled(CANCEL_SIGNALS[0])
    if reaped_rc is None or not cleaned or not orphans_reaped:
        return None
    return reaped_rc


def run_leg(leg_name: str, args: list[str], timeout_seconds: int) -> int | None:
    """Run ``cargo mutants`` with ``args`` and a bounded SIGTERM-then-kill deadline.

    The executable and subcommand are literals at the call site, each element
    of ``args`` is passed as one argv element without a shell, and the leg runs
    in a session of its own so every descendant can be found. Inherited
    ``CARGO_MUTANTS_*`` environment variables are stripped via
    ``leg_environment`` so CLI flags govern every run. Processes left in the
    leg session are killed while the unreaped ``cargo-mutants`` zombie holds the
    session ID, and child-subreaper orphan cleanup then requires ``waitpid``
    ``ECHILD`` proof before returning the exit code. Exceeding
    ``timeout_seconds`` stops the leg with ``SIGTERM`` then ``SIGKILL``. A
    ``SIGINT`` or ``SIGTERM`` recorded by ``request_cancel`` stops a running leg
    within ``LEG_POLL_SECONDS``, and ``LegCancelled`` is raised if a signal
    arrived before start, during the poll, during exit cleanup and reap, or
    during a deadline stop rather than returning ``rc`` or ``None``.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    if CANCEL_SIGNALS:
        raise LegCancelled(CANCEL_SIGNALS[0])
    try:
        proc = subprocess.Popen(
            ["cargo", "mutants", *args],
            start_new_session=True,
            env=leg_environment(os.environ),
        )
    except OSError as exc:
        err(f"{leg_name} leg failed to start cargo-mutants: {exc}")
        if CANCEL_SIGNALS:
            raise LegCancelled(CANCEL_SIGNALS[0]) from exc
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
        if wait_exited(proc.pid, min(LEG_POLL_SECONDS, remaining)):
            return reap_exited_leg(leg_name, proc)
    err(f"{leg_name} leg exceeded its {timeout_seconds}s deadline")
    stop_leg(leg_name, proc)
    if CANCEL_SIGNALS:
        raise LegCancelled(CANCEL_SIGNALS[0])
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


def count_outcome_lines(mutants_out: Path, name: str) -> int | None:
    """Count non-empty lines in ``mutants_out / name``, or return ``None``."""
    lines = read_outcome_file(mutants_out, name)
    if lines is None:
        return None
    count = 0
    for idx in range(len(lines)):
        if lines[idx]:
            count += 1
    return count


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


def check_gate_counts(caught: int, unviable: int) -> bool:
    """Verify the gate unviable ceiling, caught floor, and tested population floor."""
    passed = True
    if unviable > GATE_UNVIABLE_CEILING:
        err(
            f"gate leg: {unviable} unviable mutants exceed the ceiling of "
            f"{GATE_UNVIABLE_CEILING}; a config or code change stopped them "
            "from building"
        )
        passed = False
    elif unviable < GATE_UNVIABLE_CEILING:
        print(
            f"mutants-check: gate unviable {unviable} below ceiling "
            f"{GATE_UNVIABLE_CEILING}; lower GATE_UNVIABLE_CEILING"
        )
    if caught < GATE_CAUGHT_FLOOR:
        err(
            f"gate leg: {caught} caught mutants below the floor of "
            f"{GATE_CAUGHT_FLOOR}; a skip attribute, an exclude or a "
            "cargo-mutants change dropped mutants from the gate"
        )
        passed = False
    elif caught > GATE_CAUGHT_FLOOR:
        print(
            f"mutants-check: gate caught {caught} above floor "
            f"{GATE_CAUGHT_FLOOR}; raise GATE_CAUGHT_FLOOR"
        )
    tested = caught + unviable
    if tested < GATE_MUTANTS_FLOOR:
        err(
            f"gate leg: {tested} mutants tested below the floor of "
            f"{GATE_MUTANTS_FLOOR}; a skip attribute, an exclude or a "
            "cargo-mutants change dropped mutants from the gate"
        )
        passed = False
    elif tested > GATE_MUTANTS_FLOOR:
        print(
            f"mutants-check: gate tested {tested} above floor "
            f"{GATE_MUTANTS_FLOOR}; raise GATE_MUTANTS_FLOOR"
        )
    return passed


def run_gate_leg() -> int:
    """Execute the gate leg and verify its outcome counts.

    Writes ``cargo-mutants`` output to a new private ``tempfile`` directory
    (under ``TMPDIR``, outside the checkout unless ``TMPDIR`` points into it)
    and checks the unviable ceiling, the caught floor, and the tested
    population floor before removing it.
    """
    with tempfile.TemporaryDirectory(prefix="mutants-gate-") as tmp_dir:
        output_dir = Path(tmp_dir)
        gate_rc = run_leg(
            "gate", [*COMMON_ARGS, "--output", str(output_dir)], GATE_TIMEOUT_SECONDS
        )
        if gate_rc is None:
            return 1
        if gate_rc != 0:
            err(f"gate leg failed (cargo-mutants exit {gate_rc})")
            return 1
        mutants_out = output_dir / "mutants.out"
        unviable = count_outcome_lines(mutants_out, "unviable.txt")
        caught = count_outcome_lines(mutants_out, "caught.txt")
        if unviable is None or caught is None:
            return 1
        return 0 if check_gate_counts(caught, unviable) else 1


def main() -> int:
    """Run configuration validation, the gate leg, and the planted leg."""
    # Signals are recorded, never raised, so a leg stop cannot be interrupted
    # (cargo-mutants runs in its own session and does not get them).
    signal.signal(signal.SIGINT, request_cancel)
    signal.signal(signal.SIGTERM, request_cancel)
    config, status = load_config(CONFIG_PATH)
    if config is None:
        cancelled = cancel_status()
        return cancelled if cancelled is not None else status
    if not enable_subreaper():
        cancelled = cancel_status()
        return cancelled if cancelled is not None else 1
    try:
        leg_status = run_gate_leg()
        cancelled = cancel_status()
        if cancelled is not None:
            return cancelled
        if leg_status == 0:
            leg_status = run_planted_leg(config)
            cancelled = cancel_status()
            if cancelled is not None:
                return cancelled
        return leg_status
    except LegCancelled as exc:
        err(f"cancelled by {signal.Signals(exc.signum).name}")
        return SIGNAL_EXIT_BASE + exc.signum


if __name__ == "__main__":
    sys.exit(main())
