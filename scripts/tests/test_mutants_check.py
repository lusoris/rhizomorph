# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2
"""Replay positive, negative, and boundary fixtures for ``scripts/mutants-check.py``.

Replays gate count floor/ceiling checks, outcome line counting, planted-leg
bijection and empty-outcome verification, ``.cargo/mutants.toml`` validation,
``/proc/<pid>/stat`` parsing and session cleanup error propagation, signal
cancellation exit handling, and ``cargo mutants`` worker-bound CLI arguments.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import signal
import sys
import tempfile
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
        self.assertEqual(floor + ceiling, MOD.GATE_MUTANTS_FLOOR)

        ok, out_txt, err_txt = call_quiet(MOD.check_gate_counts, floor, ceiling)
        self.assertTrue(ok)
        self.assertEqual(out_txt, "")
        self.assertEqual(err_txt, "")

        ok, _, err_txt = call_quiet(MOD.check_gate_counts, floor, ceiling + 1)
        self.assertFalse(ok)
        self.assertIn("exceed the ceiling", err_txt)

        ok, _, err_txt = call_quiet(MOD.check_gate_counts, floor - 1, ceiling)
        self.assertFalse(ok)
        self.assertIn("caught mutants below the floor", err_txt)

        ok, _, err_txt = call_quiet(MOD.check_gate_counts, floor, ceiling - 1)
        self.assertFalse(ok)
        self.assertIn("mutants tested below the floor", err_txt)

        ok, _, err_txt = call_quiet(MOD.check_gate_counts, floor + 1, ceiling - 1)
        self.assertTrue(ok)
        self.assertEqual(err_txt, "")

        ok, out_txt, err_txt = call_quiet(MOD.check_gate_counts, floor + 1, ceiling)
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
    """Replay ``load_config`` validation and ``build_planted_args`` worker bounds."""

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
            raise AssertionError("expected MutantsConfig")
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


class ProcCleanupTests(unittest.TestCase):
    """Replay ``parse_proc_stat``, ``read_proc_state_session``, and session cleanup."""

    def test_parse_proc_stat(self) -> None:
        """Verify ``comm`` with spaces and ``)`` parses and malformed inputs fail."""
        self.assertEqual(
            MOD.parse_proc_stat("123 (a b) c) S 1 123 123 0 -1"),
            ("S", 123),
        )
        self.assertEqual(
            MOD.parse_proc_stat("123 (a b) c) R 1 77 456 0 -1"),
            ("R", 456),
        )
        self.assertIsNone(MOD.parse_proc_stat("123 missing_rparen S 1 123 123"))
        self.assertIsNone(MOD.parse_proc_stat("123 (comm) S 1 123"))
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
        self.assertEqual(res.parsed[1], os.getsid(0))


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


if __name__ == "__main__":
    unittest.main()
