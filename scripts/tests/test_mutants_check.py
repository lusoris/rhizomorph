# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2
"""Replay positive, negative, and boundary fixtures for ``scripts/mutants-check.py``.

Replays gate count floor/ceiling checks, outcome line counting, planted-leg
bijection and empty-outcome verification, ``.cargo/mutants.toml`` validation,
``/proc/<pid>/stat`` parsing and session cleanup error propagation, child
subreaper and orphan reaping checks, ``CARGO_MUTANTS_*`` environment stripping,
signal cancellation exit handling, and real Linux descendant cleanup.
"""

from __future__ import annotations

import contextlib
import errno
import importlib.util
import io
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TypeVar
from unittest import mock

T = TypeVar("T")


def load_mutants_check() -> ModuleType:
    """Load ``scripts/mutants-check.py`` as the ``mutants_check`` module."""
    script_path = Path(__file__).resolve().parent.parent / "mutants-check.py"
    spec = importlib.util.spec_from_file_location("mutants_check", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot create module spec for {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MOD = load_mutants_check()
EMPTY_FILES: dict[str, str] = {
    "caught.txt": "",
    "timeout.txt": "",
    "unviable.txt": "",
}


def call_quiet(
    func: Callable[..., T], *args: object, **kwargs: object
) -> tuple[T, str, str]:
    """Invoke ``func`` with standard output and standard error captured."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
        result = func(*args, **kwargs)
    return result, out_buf.getvalue(), err_buf.getvalue()


def write_mutants_out(base_dir: Path, files: dict[str, str]) -> Path:
    """Create a ``mutants.out`` fixture directory populated from ``files``."""
    mutants_out = base_dir / "mutants.out"
    mutants_out.mkdir(parents=True, exist_ok=True)
    names = list(files.keys())
    for idx in range(len(names)):
        name = names[idx]
        (mutants_out / name).write_text(files[name], encoding="utf-8")
    return mutants_out


class GateCountsTests(unittest.TestCase):
    """Replay ``check_gate_counts`` and ``count_outcome_lines`` fixtures."""

    def test_check_gate_counts_boundaries(self) -> None:
        """Verify caught floor, unviable ceiling, and tested population floor."""
        floor = MOD.GATE_CAUGHT_FLOOR
        ceiling = MOD.GATE_UNVIABLE_CEILING
        mutants_floor = MOD.GATE_MUTANTS_FLOOR

        pass_caught = max(floor, mutants_floor - ceiling)
        pass_unviable = ceiling
        ok, _, err_txt = call_quiet(MOD.check_gate_counts, pass_caught, pass_unviable)
        self.assertTrue(ok)
        self.assertEqual(err_txt, "")

        unviable_fail_caught = max(floor, mutants_floor - (ceiling + 1))
        ok, _, err_txt = call_quiet(
            MOD.check_gate_counts, unviable_fail_caught, ceiling + 1
        )
        self.assertFalse(ok)
        self.assertIn("exceed the ceiling", err_txt)
        self.assertNotIn("caught mutants below the floor", err_txt)
        self.assertNotIn("mutants tested below the floor", err_txt)

        min_unviable_for_pop = max(0, mutants_floor - (floor - 1))
        if min_unviable_for_pop <= ceiling:
            ok, _, err_txt = call_quiet(
                MOD.check_gate_counts, floor - 1, min_unviable_for_pop
            )
            self.assertFalse(ok)
            self.assertIn("caught mutants below the floor", err_txt)
            self.assertNotIn("exceed the ceiling", err_txt)
            self.assertNotIn("mutants tested below the floor", err_txt)
        else:
            with self.subTest(
                note=(
                    "caught = floor - 1 cannot meet GATE_MUTANTS_FLOOR within "
                    "GATE_UNVIABLE_CEILING"
                )
            ):
                ok, _, err_txt = call_quiet(MOD.check_gate_counts, floor - 1, ceiling)
                self.assertFalse(ok)
                self.assertIn("caught mutants below the floor", err_txt)
                self.assertNotIn("exceed the ceiling", err_txt)

        if floor < mutants_floor and ceiling >= 0:
            pop_fail_unviable = min(ceiling, mutants_floor - 1 - floor)
            ok, _, err_txt = call_quiet(MOD.check_gate_counts, floor, pop_fail_unviable)
            self.assertFalse(ok)
            self.assertIn("mutants tested below the floor", err_txt)
            self.assertNotIn("caught mutants below the floor", err_txt)
            self.assertNotIn("exceed the ceiling", err_txt)
        else:
            self.assertGreaterEqual(
                floor,
                mutants_floor,
                "population below GATE_MUTANTS_FLOOR is unreachable with "
                "caught >= GATE_CAUGHT_FLOOR and non-negative unviable",
            )

    def test_check_gate_counts_advisory_notes(self) -> None:
        """Emit tighten-threshold notes when counts beat configured bounds."""
        pass_caught = max(
            MOD.GATE_CAUGHT_FLOOR,
            MOD.GATE_MUTANTS_FLOOR - MOD.GATE_UNVIABLE_CEILING,
        )
        pass_unviable = MOD.GATE_UNVIABLE_CEILING
        if pass_unviable > 0:
            ok, out_txt, err_txt = call_quiet(
                MOD.check_gate_counts, pass_caught + 1, pass_unviable - 1
            )
            self.assertTrue(ok)
            self.assertEqual(err_txt, "")
            self.assertIn("lower GATE_UNVIABLE_CEILING", out_txt)

        ok, out_txt, err_txt = call_quiet(
            MOD.check_gate_counts, pass_caught + 1, pass_unviable
        )
        self.assertTrue(ok)
        self.assertEqual(err_txt, "")
        self.assertIn("raise GATE_CAUGHT_FLOOR", out_txt)

    def test_count_outcome_lines(self) -> None:
        """Verify missing outcome files return ``None`` and blank lines are ignored."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mutants_out = Path(tmp_dir)
            missing, _, err_txt = call_quiet(
                MOD.count_outcome_lines, mutants_out, "caught.txt"
            )
            self.assertIsNone(missing)
            self.assertIn("failed to read caught.txt", err_txt)

            (mutants_out / "caught.txt").write_text(
                "mutant one\n\nmutant two\n\n", encoding="utf-8"
            )
            count, _, err_txt = call_quiet(
                MOD.count_outcome_lines, mutants_out, "caught.txt"
            )
            self.assertEqual(count, 2)
            self.assertEqual(err_txt, "")


class VerifyPlantedOutputsTests(unittest.TestCase):
    """Replay ``verify_planted_outputs`` bijection and empty-outcome fixtures."""

    def compile_fixture_patterns(self, patterns: list[str]) -> list[tuple[str, object]]:
        """Compile ``patterns`` through ``compile_exclusions`` without stderr noise."""
        compiled, _, err_txt = call_quiet(
            MOD.compile_exclusions, patterns, Path("fixture")
        )
        self.assertIsNotNone(compiled)
        self.assertEqual(err_txt, "")
        if compiled is None:
            raise AssertionError("expected fixture patterns to compile")
        return compiled

    def test_verify_planted_outputs_pass(self) -> None:
        """Accept a one-to-one ``missed.txt`` match when other outcomes are empty."""
        exclusions = self.compile_fixture_patterns(["alpha_fn$", "beta_fn$"])
        with tempfile.TemporaryDirectory() as tmp_dir:
            files = {
                **EMPTY_FILES,
                "missed.txt": "src/lib.rs:10: alpha_fn\nsrc/lib.rs:20: beta_fn\n",
            }
            mutants_out = write_mutants_out(Path(tmp_dir), files)
            missed, _, err_txt = call_quiet(
                MOD.verify_planted_outputs, mutants_out, exclusions
            )
            self.assertEqual(
                missed,
                ["src/lib.rs:10: alpha_fn", "src/lib.rs:20: beta_fn"],
            )
            self.assertEqual(err_txt, "")

    def test_verify_planted_outputs_non_empty_outcomes(self) -> None:
        """Reject non-empty ``caught.txt``, ``timeout.txt``, or ``unviable.txt``."""
        exclusions = self.compile_fixture_patterns(["alpha_fn$", "beta_fn$"])
        cases = (
            ("caught.txt", "src/lib.rs:20: beta_fn\n", "non-empty caught.txt"),
            ("timeout.txt", "src/lib.rs:30: slow_fn\n", "non-empty timeout.txt"),
            ("unviable.txt", "src/lib.rs:40: broken_fn\n", "non-empty unviable.txt"),
        )
        for idx in range(len(cases)):
            bad_file, bad_text, expected_msg = cases[idx]
            with tempfile.TemporaryDirectory() as tmp_dir:
                files = {
                    **EMPTY_FILES,
                    "missed.txt": "src/lib.rs:10: alpha_fn\nsrc/lib.rs:20: beta_fn\n",
                    bad_file: bad_text,
                }
                mutants_out = write_mutants_out(Path(tmp_dir), files)
                missed, _, err_txt = call_quiet(
                    MOD.verify_planted_outputs, mutants_out, exclusions
                )
                self.assertIsNone(missed)
                self.assertIn(expected_msg, err_txt)

    def test_verify_planted_outputs_bijection_failures(self) -> None:
        """Reject zero-hit, multi-hit, duplicate-line, count, and missing-file cases."""
        cases: tuple[tuple[list[str], dict[str, str], str], ...] = (
            (
                ["alpha_fn$", "gamma_fn$"],
                {
                    **EMPTY_FILES,
                    "missed.txt": "src/lib.rs:10: alpha_fn\nsrc/lib.rs:20: beta_fn\n",
                },
                "matched 0 missed.txt lines, expected 1",
            ),
            (
                ["alpha_fn", "unique_fn$"],
                {
                    **EMPTY_FILES,
                    "missed.txt": (
                        "src/lib.rs:10: alpha_fn one\n"
                        "src/lib.rs:20: alpha_fn unique_fn\n"
                    ),
                },
                "matched 2 missed.txt lines, expected 1",
            ),
            (
                ["alpha_fn", "shared_tail$"],
                {
                    **EMPTY_FILES,
                    "missed.txt": (
                        "src/lib.rs:10: alpha_fn shared_tail\n"
                        "src/lib.rs:20: unrelated_fn\n"
                    ),
                },
                "matched duplicate missed.txt line",
            ),
            (
                ["alpha_fn$"],
                {
                    **EMPTY_FILES,
                    "missed.txt": "src/lib.rs:10: alpha_fn\nsrc/lib.rs:20: extra_fn\n",
                },
                "missed.txt line count is 2, expected 1",
            ),
            (
                ["alpha_fn$"],
                dict(EMPTY_FILES),
                "failed to read missed.txt",
            ),
        )
        for idx in range(len(cases)):
            patterns, files, expected_msg = cases[idx]
            exclusions = self.compile_fixture_patterns(patterns)
            with tempfile.TemporaryDirectory() as tmp_dir:
                mutants_out = write_mutants_out(Path(tmp_dir), files)
                missed, _, err_txt = call_quiet(
                    MOD.verify_planted_outputs, mutants_out, exclusions
                )
                self.assertIsNone(missed)
                self.assertIn(expected_msg, err_txt)


class ConfigAndArgvTests(unittest.TestCase):
    """Replay config validation, argv construction, and environment sanitization."""

    def load_toml_text(self, content: str) -> tuple[object, int, str]:
        """Write ``content`` to a temporary TOML file and call ``load_config``."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = Path(tmp_dir) / "mutants.toml"
            cfg_path.write_text(content, encoding="utf-8")
            (cfg, status), _, err_txt = call_quiet(MOD.load_config, cfg_path)
            return cfg, status, err_txt

    def test_load_config_valid(self) -> None:
        """Accept a valid ``mutants.toml`` with all supported keys."""
        toml_text = (
            'additional_cargo_args = ["--locked"]\n'
            "cap_lints = true\n"
            'exclude_re = ["first_fn$", "second_fn$"]\n'
        )
        cfg, status, err_txt = self.load_toml_text(toml_text)
        self.assertEqual(status, 0)
        self.assertEqual(err_txt, "")
        self.assertIsInstance(cfg, MOD.MutantsConfig)
        if not isinstance(cfg, MOD.MutantsConfig):
            self.fail("expected MutantsConfig")
        self.assertTrue(cfg.cap_lints)
        self.assertEqual(cfg.additional_cargo_args, ["--locked"])
        self.assertEqual(len(cfg.exclude_re), 2)

    def test_load_config_rejections(self) -> None:
        """Reject unknown keys, missing or empty exclusions, bad regex, and types."""
        cases = (
            (
                'unknown_key = 1\nexclude_re = ["ok$"]\n',
                2,
                "unsupported key",
            ),
            (
                "cap_lints = true\n",
                1,
                "omits exclude_re",
            ),
            (
                "exclude_re = []\n",
                1,
                "exclude_re is empty",
            ),
            (
                'exclude_re = ["[unterminated"]\n',
                2,
                "invalid exclude_re regex",
            ),
            (
                'cap_lints = "yes"\nexclude_re = ["ok$"]\n',
                2,
                "cap_lints",
            ),
        )
        for idx in range(len(cases)):
            toml_text, expected_status, expected_msg = cases[idx]
            cfg, status, err_txt = self.load_toml_text(toml_text)
            self.assertIsNone(cfg)
            self.assertEqual(status, expected_status)
            self.assertIn(expected_msg, err_txt)

    def test_build_planted_args_worker_bound(self) -> None:
        """Verify ``build_planted_args`` has ``--jobs 1`` once and ends with ``-F``."""
        compiled, _, _ = call_quiet(
            MOD.compile_exclusions, ["first_pat$", "last_pat$"], Path("fixture")
        )
        if compiled is None:
            raise AssertionError("expected compiled patterns")
        config = MOD.MutantsConfig(compiled, ["--locked"], True)
        args = MOD.build_planted_args(config, Path("planted-out"))
        self.assertEqual(args.count("--jobs"), 1)
        jobs_idx = args.index("--jobs")
        self.assertEqual(args[jobs_idx : jobs_idx + 2], ["--jobs", "1"])
        self.assertEqual(args[-2:], ["-F", "last_pat$"])

    def test_leg_environment_strips_cargo_mutants_vars(self) -> None:
        """Drop ``CARGO_MUTANTS_*`` keys, keep the rest, leave the input unchanged."""
        source = {
            "PATH": "/usr/bin",
            "CARGO_HOME": "/tmp/cargo",
            "CARGO_MUTANTS_OUTPUT": "/tmp/stale-out",
            "CARGO_MUTANTS_JOBS": "16",
            "CARGO_MUTANTS_MINIMUM_TEST_TIMEOUT": "300",
            "CARGO_MUTANTS_TRACE_LEVEL": "debug",
            "CARGO_MUTANTS_EXTRA": "1",
        }
        snapshot = dict(source)
        cleaned = MOD.leg_environment(source)
        self.assertEqual(source, snapshot)
        self.assertEqual(
            cleaned,
            {
                "PATH": "/usr/bin",
                "CARGO_HOME": "/tmp/cargo",
            },
        )

    def test_gate_leg_passes_explicit_output_dot(self) -> None:
        """Verify ``run_gate_leg`` passes ``--output .`` to ``run_leg``."""
        with (
            mock.patch.object(MOD, "run_leg", return_value=1) as mock_run_leg,
            mock.patch.object(Path, "exists", return_value=False),
        ):
            rc, _, err_txt = call_quiet(MOD.run_gate_leg)
        self.assertEqual(rc, 1)
        self.assertIn("gate leg failed", err_txt)
        mock_run_leg.assert_called_once()
        leg_name, leg_args, leg_timeout = mock_run_leg.call_args.args
        self.assertEqual(leg_name, "gate")
        self.assertEqual(leg_timeout, MOD.GATE_TIMEOUT_SECONDS)
        out_idx = leg_args.index("--output")
        self.assertEqual(leg_args[out_idx : out_idx + 2], ["--output", "."])

    def test_run_leg_passes_sanitized_env_to_popen(self) -> None:
        """Verify ``run_leg`` strips ``CARGO_MUTANTS_OUTPUT`` from ``Popen`` ``env``."""
        MOD.CANCEL_SIGNALS.clear()
        fake_proc = mock.MagicMock()
        fake_proc.pid = 777
        fake_proc.wait.return_value = 0
        env_overrides = {
            "CARGO_MUTANTS_OUTPUT": "/tmp/override",
            "CARGO_MUTANTS_JOBS": "9",
            "MUTANTS_CHECK_KEEP": "present",
        }
        with (
            mock.patch.dict(os.environ, env_overrides, clear=False),
            mock.patch.object(
                MOD.subprocess, "Popen", return_value=fake_proc
            ) as mock_popen,
            mock.patch.object(MOD, "wait_exited", return_value=True),
            mock.patch.object(MOD, "reap_exited_leg", return_value=0),
        ):
            rc, _, err_txt = call_quiet(MOD.run_leg, "gate", ["--output", "."], 5)
        self.assertEqual(rc, 0)
        self.assertEqual(err_txt, "")
        popen_env = mock_popen.call_args.kwargs["env"]
        self.assertNotIn("CARGO_MUTANTS_OUTPUT", popen_env)
        self.assertNotIn("CARGO_MUTANTS_JOBS", popen_env)
        self.assertEqual(popen_env.get("MUTANTS_CHECK_KEEP"), "present")


class ProcCleanupTests(unittest.TestCase):
    """Replay ``parse_proc_stat``, ``read_proc_state_session``, and session cleanup."""

    def test_parse_proc_stat(self) -> None:
        """Verify ``(state, ppid, session)`` parses and malformed inputs fail."""
        self.assertEqual(
            MOD.parse_proc_stat("123 (a b) c) S 1 123 123 0 -1"),
            ("S", 1, 123),
        )
        self.assertEqual(
            MOD.parse_proc_stat("123 (a b) c) R 42 77 456 0 -1"),
            ("R", 42, 456),
        )
        self.assertIsNone(MOD.parse_proc_stat("123 missing_rparen S 1 123 123"))
        self.assertIsNone(MOD.parse_proc_stat("123 (comm) S 1 123"))
        self.assertIsNone(MOD.parse_proc_stat("123 (comm) S bad_ppid 123 123 0"))
        self.assertIsNone(MOD.parse_proc_stat("123 (comm) S 1 123 not_an_int 0"))

    def test_read_proc_state_session_outcomes(self) -> None:
        """Distinguish vanished processes from unreadable or garbled ``stat`` files."""
        with mock.patch.object(
            Path, "read_text", side_effect=FileNotFoundError("gone")
        ):
            res = MOD.read_proc_state_session("101")
            self.assertEqual(res.status, MOD.PROC_STAT_VANISHED)
            self.assertIsNone(res.parsed)
            self.assertIsNone(res.error)

        with mock.patch.object(
            Path, "read_text", side_effect=ProcessLookupError("esrch")
        ):
            res = MOD.read_proc_state_session("102")
            self.assertEqual(res.status, MOD.PROC_STAT_VANISHED)
            self.assertIsNone(res.parsed)
            self.assertIsNone(res.error)

        with mock.patch.object(
            Path, "read_text", side_effect=PermissionError("denied")
        ):
            res = MOD.read_proc_state_session("103")
            self.assertEqual(res.status, MOD.PROC_STAT_FAILED)
            self.assertIsNone(res.parsed)
            self.assertIsNotNone(res.error)

        with mock.patch.object(Path, "read_text", return_value="104 garbled"):
            res = MOD.read_proc_state_session("104")
            self.assertEqual(res.status, MOD.PROC_STAT_FAILED)
            self.assertIsNone(res.parsed)
            self.assertIsNotNone(res.error)

        with mock.patch.object(Path, "read_text") as mock_read:
            res = MOD.read_proc_state_session("self")
            self.assertEqual(res.status, MOD.PROC_STAT_VANISHED)
            mock_read.assert_not_called()

    def test_session_live_pids_failure_and_vanished(self) -> None:
        """Propagate unreadable ``stat`` as ``None`` while skipping vanished entries."""
        with (
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=["self", "4242", "4243"]),
            mock.patch.object(
                Path,
                "read_text",
                side_effect=[
                    PermissionError("eacces"),
                    "4243 (worker) S 1 500 500 0 -1",
                ],
            ),
        ):
            pids, _, err_txt = call_quiet(MOD.session_live_pids, 500)
            self.assertIsNone(pids)
            self.assertIn("4242", err_txt)

        with (
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=["self", "4242", "4243"]),
            mock.patch.object(
                Path,
                "read_text",
                side_effect=[
                    "4242 broken_stat",
                    "4243 (worker) S 1 500 500 0 -1",
                ],
            ),
        ):
            pids, _, err_txt = call_quiet(MOD.session_live_pids, 500)
            self.assertIsNone(pids)
            self.assertIn("4242", err_txt)

        with (
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=["self", "4242", "4243"]),
            mock.patch.object(
                Path,
                "read_text",
                side_effect=[
                    FileNotFoundError("vanished"),
                    "4243 (worker) S 1 500 500 0 -1",
                ],
            ),
        ):
            pids, _, err_txt = call_quiet(MOD.session_live_pids, 500)
            self.assertEqual(pids, [4243])
            self.assertEqual(err_txt, "")

    def test_session_live_pids_zombie_and_dead_states(self) -> None:
        """Include zombie leaders with live threads while skipping exited Z and X."""
        poller_live = mock.MagicMock()
        poller_live.poll.return_value = []
        poller_exited = mock.MagicMock()
        poller_exited.poll.return_value = [(11, select.POLLIN)]
        entries = ["500", "601", "602", "603", "604"]
        stats = [
            "500 (leader) Z 1 500 500 0 -1",
            "601 (live_threads) Z 500 500 500 0 -1",
            "602 (exited_group) Z 500 500 500 0 -1",
            "603 (dead_proc) X 500 500 500 0 -1",
            "604 (vanished_z) Z 500 500 500 0 -1",
        ]
        with (
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=entries),
            mock.patch.object(Path, "read_text", side_effect=stats),
            mock.patch.object(
                os,
                "pidfd_open",
                side_effect=[10, 11, ProcessLookupError("gone")],
                create=True,
            ) as mock_open,
            mock.patch.object(os, "close") as mock_close,
            mock.patch.object(select, "poll", side_effect=[poller_live, poller_exited]),
        ):
            pids, _, err_txt = call_quiet(MOD.session_live_pids, 500)
        self.assertEqual(pids, [601])
        self.assertEqual(err_txt, "")
        opened_pids: list[int] = []
        for idx in range(len(mock_open.call_args_list)):
            opened_pids.append(mock_open.call_args_list[idx].args[0])
        self.assertEqual(opened_pids, [601, 602, 604])
        self.assertEqual(mock_close.call_count, 2)

    def test_session_live_pids_pidfd_errors_fail_closed(self) -> None:
        """Return ``None`` when ``pidfd_open`` or ``close`` fails on a zombie entry."""
        with (
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=["601"]),
            mock.patch.object(
                Path, "read_text", return_value="601 (z) Z 500 500 500 0 -1"
            ),
            mock.patch.object(
                os, "pidfd_open", side_effect=PermissionError("denied"), create=True
            ),
        ):
            pids, _, err_txt = call_quiet(MOD.session_live_pids, 500)
            self.assertIsNone(pids)
            self.assertIn("601", err_txt)

        poller_exited = mock.MagicMock()
        poller_exited.poll.return_value = [(12, select.POLLIN)]
        with (
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=["602"]),
            mock.patch.object(
                Path, "read_text", return_value="602 (z) Z 500 500 500 0 -1"
            ),
            mock.patch.object(os, "pidfd_open", return_value=12, create=True),
            mock.patch.object(select, "poll", return_value=poller_exited),
            mock.patch.object(os, "close", side_effect=OSError("bad fd")),
        ):
            pids, _, err_txt = call_quiet(MOD.session_live_pids, 500)
            self.assertIsNone(pids)
            self.assertIn("602", err_txt)

    def test_kill_verified_recheck_outcomes(self) -> None:
        """Verify pidfd re-read skips vanished or foreign PIDs and fails on errors."""
        with (
            mock.patch.object(os, "pidfd_open", return_value=9, create=True),
            mock.patch.object(os, "close"),
            mock.patch.object(signal, "pidfd_send_signal", create=True) as mock_send,
        ):
            with mock.patch.object(
                Path, "read_text", side_effect=FileNotFoundError("gone")
            ):
                ok, _, err_txt = call_quiet(MOD.kill_verified, "gate", 300, 500)
                self.assertTrue(ok)
                self.assertEqual(err_txt, "")
                mock_send.assert_not_called()

            with mock.patch.object(
                Path, "read_text", side_effect=PermissionError("denied")
            ):
                ok, _, err_txt = call_quiet(MOD.kill_verified, "gate", 300, 500)
                self.assertFalse(ok)
                self.assertIn("300", err_txt)
                mock_send.assert_not_called()

            with mock.patch.object(
                Path, "read_text", return_value="300 (other) S 1 999 999 0 -1"
            ):
                ok, _, err_txt = call_quiet(MOD.kill_verified, "gate", 300, 500)
                self.assertTrue(ok)
                self.assertEqual(err_txt, "")
                mock_send.assert_not_called()

            with mock.patch.object(
                Path, "read_text", return_value="300 (child) S 1 500 500 0 -1"
            ):
                ok, _, err_txt = call_quiet(MOD.kill_verified, "gate", 300, 500)
                self.assertTrue(ok)
                self.assertEqual(err_txt, "")
                mock_send.assert_called_once_with(9, signal.SIGKILL)

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "requires Linux /proc filesystem"
    )
    def test_live_proc_self_stat(self) -> None:
        """Read the current process entry from live ``/proc`` on Linux."""
        res = MOD.read_proc_state_session(str(os.getpid()))
        self.assertEqual(res.status, MOD.PROC_STAT_PARSED)
        self.assertIsNotNone(res.parsed)
        if res.parsed is None:
            raise AssertionError("expected live /proc stat to parse")
        self.assertEqual(res.parsed[1], os.getppid())
        self.assertEqual(res.parsed[2], os.getsid(0))


class SubreaperAndOrphanTests(unittest.TestCase):
    """Replay ``enable_subreaper``, ``reap_orphans``, and reap ordering fixtures."""

    def setUp(self) -> None:
        """Clear ``CANCEL_SIGNALS`` before and after each test."""
        MOD.CANCEL_SIGNALS.clear()
        self.addCleanup(MOD.CANCEL_SIGNALS.clear)

    def test_enable_subreaper_and_main_fail_closed(self) -> None:
        """Fail closed when ``prctl`` fails and return ``1`` from ``main``."""
        fake_libc = mock.MagicMock()
        fake_libc.prctl.return_value = -1
        with (
            mock.patch.object(MOD.ctypes, "CDLL", return_value=fake_libc),
            mock.patch.object(MOD.ctypes, "get_errno", return_value=errno.EPERM),
        ):
            ok, _, err_txt = call_quiet(MOD.enable_subreaper)
        self.assertFalse(ok)
        self.assertIn(os.strerror(errno.EPERM), err_txt)

        fake_libc.prctl.return_value = 0
        with mock.patch.object(MOD.ctypes, "CDLL", return_value=fake_libc):
            ok, _, err_txt = call_quiet(MOD.enable_subreaper)
        self.assertTrue(ok)
        self.assertEqual(err_txt, "")

        compiled, _, _ = call_quiet(MOD.compile_exclusions, ["pat$"], Path("fixture"))
        cfg = MOD.MutantsConfig(compiled or [], [], True)
        with (
            mock.patch.object(signal, "signal"),
            mock.patch.object(MOD, "load_config", return_value=(cfg, 0)),
            mock.patch.object(MOD, "enable_subreaper", return_value=False),
            mock.patch.object(MOD, "run_gate_leg") as mock_gate,
        ):
            rc, _, _ = call_quiet(MOD.main)
        self.assertEqual(rc, 1)
        mock_gate.assert_not_called()

    def test_reap_orphans_drain_and_kill_rounds(self) -> None:
        """Prove ``ECHILD`` immediately, after zombie drain, and after pidfd kill."""
        with mock.patch.object(os, "waitpid", side_effect=ChildProcessError("echild")):
            ok, _, err_txt = call_quiet(MOD.reap_orphans, "gate")
        self.assertTrue(ok)
        self.assertEqual(err_txt, "")

        with mock.patch.object(
            os, "waitpid", side_effect=[(801, 0), ChildProcessError("echild")]
        ):
            ok, _, err_txt = call_quiet(MOD.reap_orphans, "gate")
        self.assertTrue(ok)
        self.assertEqual(err_txt, "")

        own_pid = os.getpid()
        child_stat = f"802 (orphan) S {own_pid} 802 802 0 -1"
        with (
            mock.patch.object(
                os,
                "waitpid",
                side_effect=[(0, 0), (802, 0), ChildProcessError("echild")],
            ),
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=["802"]),
            mock.patch.object(Path, "read_text", side_effect=[child_stat, child_stat]),
            mock.patch.object(os, "pidfd_open", return_value=14, create=True),
            mock.patch.object(os, "close"),
            mock.patch.object(signal, "pidfd_send_signal", create=True) as mock_send,
            mock.patch.object(time, "sleep"),
        ):
            ok, _, err_txt = call_quiet(MOD.reap_orphans, "gate")
        self.assertTrue(ok)
        self.assertEqual(err_txt, "")
        mock_send.assert_called_once_with(14, signal.SIGKILL)

    def test_reap_orphans_failure_paths(self) -> None:
        """Fail closed on persistent live descendants, drain cap, or ``/proc`` error."""
        with (
            mock.patch.object(os, "waitpid", return_value=(0, 0)),
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=[]),
            mock.patch.object(time, "sleep"),
        ):
            ok, _, err_txt = call_quiet(MOD.reap_orphans, "gate")
        self.assertFalse(ok)
        self.assertIn(
            f"descendants still running after {MOD.CLEANUP_ROUNDS} rounds", err_txt
        )

        with (
            mock.patch.object(os, "waitpid", return_value=(0, 0)),
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", side_effect=PermissionError("denied")),
        ):
            ok, _, err_txt = call_quiet(MOD.reap_orphans, "gate")
        self.assertFalse(ok)
        self.assertIn("/proc", err_txt)

        with (
            mock.patch.object(MOD, "REAP_DRAIN_LIMIT", 2),
            mock.patch.object(os, "waitpid", return_value=(888, 0)),
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch.object(os, "listdir", return_value=[]),
            mock.patch.object(time, "sleep"),
        ):
            ok, _, err_txt = call_quiet(MOD.reap_orphans, "gate")
        self.assertFalse(ok)
        self.assertIn("descendants still running", err_txt)

    def test_reap_exited_leg_order_and_failure_propagation(self) -> None:
        """Call ``reap_orphans`` only after ``proc.wait`` and propagate failure."""
        events: list[str] = []
        fake_proc = mock.MagicMock()
        fake_proc.pid = 700

        def rec_session(_leg: str, _sid: int, _reason: str) -> bool:
            """Record ``kill_session_leftovers`` in ``events``."""
            events.append("session")
            return True

        def rec_wait(*_args: object, **_kwargs: object) -> int:
            """Record ``proc.wait`` in ``events``."""
            events.append("wait")
            return 0

        def rec_orphans(_leg: str) -> bool:
            """Record ``reap_orphans`` in ``events``."""
            events.append("orphans")
            return True

        fake_proc.wait.side_effect = rec_wait
        with (
            mock.patch.object(MOD, "kill_session_leftovers", side_effect=rec_session),
            mock.patch.object(MOD, "reap_orphans", side_effect=rec_orphans),
        ):
            rc, _, err_txt = call_quiet(MOD.reap_exited_leg, "gate", fake_proc)
        self.assertEqual(rc, 0)
        self.assertEqual(err_txt, "")
        self.assertEqual(events, ["session", "wait", "orphans"])

        fake_proc.wait.side_effect = None
        fake_proc.wait.return_value = 0
        with (
            mock.patch.object(MOD, "kill_session_leftovers", return_value=True),
            mock.patch.object(MOD, "reap_orphans", return_value=False),
        ):
            rc, _, _ = call_quiet(MOD.reap_exited_leg, "gate", fake_proc)
        self.assertIsNone(rc)

        fake_proc.wait.side_effect = subprocess.TimeoutExpired(["cargo"], 1)
        with (
            mock.patch.object(MOD, "kill_session_leftovers", return_value=True),
            mock.patch.object(MOD, "reap_orphans") as mock_orphans,
        ):
            rc, _, err_txt = call_quiet(MOD.reap_exited_leg, "gate", fake_proc)
        self.assertIsNone(rc)
        self.assertIn("did not reap", err_txt)
        mock_orphans.assert_not_called()

    def test_stop_leg_reaps_orphans_after_wait(self) -> None:
        """Call ``reap_orphans`` after ``proc.wait`` in ``stop_leg`` and log failure."""
        events: list[str] = []
        fake_proc = mock.MagicMock()
        fake_proc.pid = 701

        def rec_wait(*_args: object, **_kwargs: object) -> int:
            """Record ``proc.wait`` in ``events``."""
            events.append("wait")
            return 0

        def rec_orphans_fail(_leg: str) -> bool:
            """Record ``reap_orphans`` in ``events`` and return ``False``."""
            events.append("orphans")
            return False

        fake_proc.wait.side_effect = rec_wait
        with (
            mock.patch.object(MOD, "signal_leg"),
            mock.patch.object(MOD, "wait_exited", return_value=True),
            mock.patch.object(MOD, "kill_session_leftovers", return_value=True),
            mock.patch.object(MOD, "reap_orphans", side_effect=rec_orphans_fail),
        ):
            _, _, err_txt = call_quiet(MOD.stop_leg, "gate", fake_proc)
        self.assertEqual(events, ["wait", "orphans"])
        self.assertIn("descendants", err_txt)


class CancellationTests(unittest.TestCase):
    """Replay ``cancel_status``, ``run_leg``, and ``main`` cancellation handling."""

    def setUp(self) -> None:
        """Clear ``CANCEL_SIGNALS`` before and after each test."""
        MOD.CANCEL_SIGNALS.clear()
        self.addCleanup(MOD.CANCEL_SIGNALS.clear)

    def test_cancel_status_helper(self) -> None:
        """Return ``128 + signum`` when cancelled and ``None`` when clear."""
        status, _, err_txt = call_quiet(MOD.cancel_status)
        self.assertIsNone(status)
        self.assertEqual(err_txt, "")

        MOD.CANCEL_SIGNALS.append(int(signal.SIGTERM))
        status, _, err_txt = call_quiet(MOD.cancel_status)
        self.assertEqual(status, MOD.SIGNAL_EXIT_BASE + int(signal.SIGTERM))
        self.assertIn("cancelled by SIGTERM", err_txt)

    def test_main_honours_late_cancel_after_legs(self) -> None:
        """Return ``128 + signum`` if a signal arrives after ``run_leg`` returns."""
        compiled, _, _ = call_quiet(MOD.compile_exclusions, ["pat$"], Path("fixture"))
        cfg = MOD.MutantsConfig(compiled or [], [], True)

        def cancel_in_planted(_cfg: object) -> int:
            """Simulate ``SIGTERM`` arriving during planted-leg verification."""
            MOD.CANCEL_SIGNALS.append(int(signal.SIGTERM))
            return 0

        with (
            mock.patch.object(signal, "signal"),
            mock.patch.object(MOD, "load_config", return_value=(cfg, 0)),
            mock.patch.object(MOD, "enable_subreaper", return_value=True),
            mock.patch.object(MOD, "run_gate_leg", return_value=0),
            mock.patch.object(MOD, "run_planted_leg", side_effect=cancel_in_planted),
        ):
            rc, _, err_txt = call_quiet(MOD.main)
            self.assertEqual(rc, MOD.SIGNAL_EXIT_BASE + int(signal.SIGTERM))
            self.assertIn("cancelled by SIGTERM", err_txt)

        MOD.CANCEL_SIGNALS.clear()

        def cancel_in_gate() -> int:
            """Simulate ``SIGINT`` arriving after ``run_leg`` in ``run_gate_leg``."""
            MOD.CANCEL_SIGNALS.append(int(signal.SIGINT))
            return 1

        with (
            mock.patch.object(signal, "signal"),
            mock.patch.object(MOD, "load_config", return_value=(cfg, 0)),
            mock.patch.object(MOD, "enable_subreaper", return_value=True),
            mock.patch.object(MOD, "run_gate_leg", side_effect=cancel_in_gate),
            mock.patch.object(MOD, "run_planted_leg") as mock_planted,
        ):
            rc, _, err_txt = call_quiet(MOD.main)
            self.assertEqual(rc, MOD.SIGNAL_EXIT_BASE + int(signal.SIGINT))
            self.assertIn("cancelled by SIGINT", err_txt)
            mock_planted.assert_not_called()

    def test_run_leg_raises_on_cleanup_or_deadline_cancel(self) -> None:
        """Raise ``LegCancelled`` when cancelled during cleanup or deadline stop."""
        fake_proc = mock.MagicMock()
        fake_proc.pid = 777
        fake_proc.wait.return_value = 0

        def cancel_during_cleanup(_leg: str, _sid: int, _reason: str) -> bool:
            """Record ``SIGTERM`` while ``kill_session_leftovers`` runs."""
            MOD.CANCEL_SIGNALS.append(int(signal.SIGTERM))
            return True

        with (
            mock.patch.object(MOD.subprocess, "Popen", return_value=fake_proc),
            mock.patch.object(MOD, "wait_exited", return_value=True),
            mock.patch.object(
                MOD, "kill_session_leftovers", side_effect=cancel_during_cleanup
            ),
            mock.patch.object(MOD, "reap_orphans", return_value=True),
        ):
            with self.assertRaises(MOD.LegCancelled) as ctx:
                call_quiet(MOD.run_leg, "gate", [], 5)
            self.assertEqual(ctx.exception.signum, int(signal.SIGTERM))

        MOD.CANCEL_SIGNALS.clear()

        def cancel_during_stop(_leg: str, _proc: object) -> None:
            """Record ``SIGINT`` while ``stop_leg`` runs after a deadline."""
            MOD.CANCEL_SIGNALS.append(int(signal.SIGINT))

        with (
            mock.patch.object(MOD.subprocess, "Popen", return_value=fake_proc),
            mock.patch.object(MOD, "wait_exited", return_value=False),
            mock.patch.object(MOD, "stop_leg", side_effect=cancel_during_stop),
        ):
            with self.assertRaises(MOD.LegCancelled) as ctx:
                call_quiet(MOD.run_leg, "gate", [], 0)
            self.assertEqual(ctx.exception.signum, int(signal.SIGINT))


@unittest.skipUnless(
    sys.platform.startswith("linux") and hasattr(os, "pidfd_open"),
    "requires Linux pidfd support",
)
class RealDescendantCleanupTests(unittest.TestCase):
    """Exercise live descendant cleanup on timeout and immediate exit paths."""

    def setUp(self) -> None:
        """Create temporary stub/FIFO fixtures and enable child subreaper."""
        MOD.CANCEL_SIGNALS.clear()
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="mutants-descendant-")
        self.base = Path(self.tmp_dir.name)
        self.fifo_path = self.base / "grandchild.fifo"
        self.ready_path = self.base / "ready.fifo"
        self.pid_file = self.base / "grandchild.pid"
        self.stub_path = self.base / "cargo"
        os.mkfifo(self.fifo_path, 0o600)
        os.mkfifo(self.ready_path, 0o600)
        self.assertTrue(MOD.enable_subreaper())
        self.fifo_fd = os.open(self.fifo_path, os.O_RDONLY | os.O_NONBLOCK)

    def tearDown(self) -> None:
        """Close the FIFO, kill any leaked grandchild via pidfd, and remove temp dir."""
        MOD.CANCEL_SIGNALS.clear()
        if self.fifo_fd >= 0:
            with contextlib.suppress(OSError):
                os.close(self.fifo_fd)
            self.fifo_fd = -1
        if self.pid_file.is_file():
            raw_pid = self.pid_file.read_text(encoding="utf-8").strip()
            if raw_pid.isascii() and raw_pid.isdigit():
                pid = int(raw_pid)
                if pid > 1:
                    self._kill_leftover_pid(pid)
        for _ in range(16):
            try:
                reaped_pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if reaped_pid == 0:
                break
        self.tmp_dir.cleanup()

    def _kill_leftover_pid(self, pid: int) -> None:
        """Send ``SIGKILL`` to ``pid`` above ``1`` via pidfd when still present."""
        if pid <= 1:
            return
        try:
            fd = os.pidfd_open(pid)
        except (FileNotFoundError, ProcessLookupError, OSError):
            return
        try:
            with contextlib.suppress(ProcessLookupError, OSError):
                signal.pidfd_send_signal(fd, signal.SIGKILL)
        finally:
            with contextlib.suppress(OSError):
                os.close(fd)

    def _write_cargo_stub(self, launcher_prefix: str, tail_cmd: str) -> None:
        """Write an executable ``cargo`` shell stub spawning a FIFO-holding child."""
        script = (
            "#!/bin/sh\n"
            f"{launcher_prefix} sh -c '\n"
            '  printf "%s\\n" "$$" > "$1"\n'
            '  exec 3>"$2"\n'
            '  printf "x" >&3\n'
            '  printf "r\\n" > "$3"\n'
            "  exec sleep 60\n"
            f'\' sh "{self.pid_file}" "{self.fifo_path}" "{self.ready_path}" '
            "</dev/null >/dev/null 2>&1 &\n"
            f'read -r _ < "{self.ready_path}"\n'
            f"{tail_cmd}\n"
        )
        self.stub_path.write_text(script, encoding="utf-8")
        os.chmod(self.stub_path, 0o755)

    def _assert_fifo_byte_then_eof(self) -> None:
        """Verify the grandchild wrote one byte and every writer closed the FIFO."""
        first = os.read(self.fifo_fd, 1)
        self.assertEqual(first, b"x")
        try:
            second = os.read(self.fifo_fd, 1)
        except BlockingIOError as exc:
            self.fail(f"grandchild writer still alive holding FIFO write end: {exc}")
        self.assertEqual(second, b"")

    def test_timeout_stops_real_descendant(self) -> None:
        """Stop a timed-out stub and verify its background grandchild reaches EOF."""
        self._write_cargo_stub("", "exec sleep 60")
        prepended_path = f"{self.base}{os.pathsep}{os.environ.get('PATH', '')}"
        with (
            mock.patch.dict(os.environ, {"PATH": prepended_path}),
            mock.patch.object(MOD, "TERMINATE_GRACE_SECONDS", 1),
        ):
            rc, _, err_txt = call_quiet(MOD.run_leg, "gate", [], 2)
        self.assertIsNone(rc)
        self.assertIn("exceeded its 2s deadline", err_txt)
        self._assert_fifo_byte_then_eof()

    def test_exit_reaps_setsid_orphan_before_returning(self) -> None:
        """Kill and reap a ``setsid`` grandchild before returning exit code ``0``."""
        # Kills mutation reap_orphans -> return True, which keeps grandchild alive.
        self._write_cargo_stub("setsid", "exit 0")
        prepended_path = f"{self.base}{os.pathsep}{os.environ.get('PATH', '')}"
        with mock.patch.dict(os.environ, {"PATH": prepended_path}):
            rc, _, err_txt = call_quiet(MOD.run_leg, "gate", [], 5)
        self.assertEqual(rc, 0)
        self.assertEqual(err_txt, "")
        self._assert_fifo_byte_then_eof()


if __name__ == "__main__":
    unittest.main()
