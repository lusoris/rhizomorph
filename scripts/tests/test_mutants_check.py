# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2
"""Replay positive, negative, and boundary fixtures for ``scripts/mutants-check.py``.

Replays gate count floor/ceiling checks, outcome line counting, planted-leg
bijection and empty-outcome verification, Cargo config and runner-cap checks,
``/proc/<pid>/stat`` parsing and session cleanup error propagation, child
subreaper and orphan reaping checks, Cargo environment stripping,
signal cancellation exit handling, and real Linux descendant cleanup.
"""

from __future__ import annotations

import contextlib
import errno
import importlib.util
import io
import json
import os
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import BinaryIO, TypeVar
from unittest import mock

if sys.platform.startswith("linux"):
    import resource

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
CAPPED_CARGO_ARGS = (
    f"additional_cargo_args = {json.dumps(['--locked', MOD.TEST_RUNNER_CAP_ARG])}\n"
)
EMPTY_FILES: dict[str, str] = {
    "caught.txt": "",
    "timeout.txt": "",
    "unviable.txt": "",
}


def address_space_skip_reason(
    soft: int, hard: int, cap: int, *, infinity: int, needs_distinct_soft: bool
) -> str | None:
    """Explain when inherited RLIMIT_AS values prevent a meaningful capped run."""
    if hard != infinity and hard < cap:
        return f"prlimit cannot raise the inherited hard RLIMIT_AS of {hard} to {cap}"
    if needs_distinct_soft and soft == cap:
        return (
            f"inherited soft RLIMIT_AS already equals {cap}, so a runner "
            "that skips prlimit would still pass the canary"
        )
    return None


def call_quiet(
    func: Callable[..., T], *args: object, **kwargs: object
) -> tuple[T, str, str]:
    """Invoke ``func`` with standard output and standard error captured."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
        result = func(*args, **kwargs)
    return result, out_buf.getvalue(), err_buf.getvalue()


@contextlib.contextmanager
def temporary_address_space_limit(target: int) -> Iterator[None]:
    """Set a test's soft RLIMIT_AS without changing its hard limit."""
    original = resource.getrlimit(resource.RLIMIT_AS)
    _, hard = original
    soft = target if hard == resource.RLIM_INFINITY else min(target, hard)
    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_AS, original)


def skip_for_inherited_limits(
    case: unittest.TestCase, *, needs_distinct_soft: bool
) -> None:
    """Skip ``case`` when the inherited RLIMIT_AS decides its capped run."""
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    reason = address_space_skip_reason(
        soft,
        hard,
        MOD.TEST_RUNNER_CAP_BYTES,
        infinity=resource.RLIM_INFINITY,
        needs_distinct_soft=needs_distinct_soft,
    )
    if reason is not None:
        case.skipTest(reason)


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
            CAPPED_CARGO_ARGS
            + 'cap_lints = true\nexclude_re = ["first_fn$", "second_fn$"]\n'
        )
        cfg, status, err_txt = self.load_toml_text(toml_text)
        self.assertEqual(status, 0)
        self.assertEqual(err_txt, "")
        self.assertIsInstance(cfg, MOD.MutantsConfig)
        if not isinstance(cfg, MOD.MutantsConfig):
            self.fail("expected MutantsConfig")
        self.assertTrue(cfg.cap_lints)
        self.assertEqual(
            cfg.additional_cargo_args, ["--locked", MOD.TEST_RUNNER_CAP_ARG]
        )
        self.assertEqual(len(cfg.exclude_re), 2)

    def test_load_config_requires_exact_test_runner_cap(self) -> None:
        """Reject a missing runner cap and a runner with a different limit."""
        different_cap = MOD.TEST_RUNNER_CAP_ARG.replace(
            "--as=4294967296", "--as=8589934592"
        )
        cases = (["--locked"], ["--locked", different_cap])
        for idx in range(len(cases)):
            cargo_args = json.dumps(cases[idx])
            with self.subTest(additional_cargo_args=cases[idx]):
                cfg, status, err_txt = self.load_toml_text(
                    f'additional_cargo_args = {cargo_args}\nexclude_re = ["ok$"]\n'
                )
                self.assertEqual(status, 2)
                self.assertIsNone(cfg)
                self.assertIn("lacks the test runner memory cap", err_txt)
                if different_cap in cases[idx]:
                    self.assertIn("unsupported additional_cargo_args", err_txt)
                    self.assertIn("--as=8589934592", err_txt)

    def test_test_runner_cap_arg_is_unchanged(self) -> None:
        """Match the exact argument stored in mutants.toml."""
        self.assertEqual(
            MOD.TEST_RUNNER_CAP_ARG,
            """--config=target.'cfg(target_os = "linux")'.runner=["prlimit", "--as=4294967296"]""",
        )

    def test_load_config_rejects_cargo_args_outside_allow_list(self) -> None:
        """Reject runner overrides and unrelated arguments alongside the cap."""
        cases = ('--config=target.x86_64-unknown-linux-gnu.runner=["env"]', "--offline")
        for idx in range(len(cases)):
            arg = cases[idx]
            with self.subTest(arg=arg):
                cargo_args = json.dumps(["--locked", MOD.TEST_RUNNER_CAP_ARG, arg])
                cfg, status, err_txt = self.load_toml_text(
                    f'additional_cargo_args = {cargo_args}\nexclude_re = ["ok$"]\n'
                )
                self.assertIsNone(cfg)
                self.assertEqual(status, 2)
                self.assertIn("mutants.toml", err_txt)
                self.assertIn(arg, err_txt)

    def test_repository_config_has_test_runner_cap(self) -> None:
        """Load the checkout config with its runner cap from a different directory."""
        repo_root = Path(MOD.__file__).resolve().parent.parent
        self.assertTrue(MOD.CONFIG_PATH.is_absolute())
        self.assertEqual(MOD.CONFIG_PATH, repo_root / ".cargo/mutants.toml")
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                (cfg, status), _, err_txt = call_quiet(MOD.load_config, MOD.CONFIG_PATH)
            finally:
                os.chdir(previous_cwd)
        self.assertEqual(status, 0, err_txt)
        self.assertIsInstance(cfg, MOD.MutantsConfig)
        self.assertIn(MOD.TEST_RUNNER_CAP_ARG, cfg.additional_cargo_args)

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
            cfg, status, err_txt = self.load_toml_text(CAPPED_CARGO_ARGS + toml_text)
            self.assertIsNone(cfg)
            self.assertEqual(status, expected_status)
            self.assertIn(expected_msg, err_txt)

    def test_build_planted_args_preserves_worker_bound_and_runner_cap(self) -> None:
        """Pass the cap as one argument, set ``--jobs 1`` once, and end with ``-F``."""
        compiled, _, _ = call_quiet(
            MOD.compile_exclusions, ["first_pat$", "last_pat$"], Path("fixture")
        )
        if compiled is None:
            raise AssertionError("expected compiled patterns")
        config = MOD.MutantsConfig(
            compiled, ["--locked", MOD.TEST_RUNNER_CAP_ARG], True
        )
        args = MOD.build_planted_args(config, Path("planted-out"))
        self.assertEqual(args.count("--jobs"), 1)
        jobs_idx = args.index("--jobs")
        self.assertEqual(args[jobs_idx : jobs_idx + 2], ["--jobs", "1"])
        self.assertIn(f"--cargo-arg={MOD.TEST_RUNNER_CAP_ARG}", args)
        self.assertEqual(args[-2:], ["-F", "last_pat$"])

    def test_common_args_select_both_packages(self) -> None:
        """Select both packages for the gate and planted legs."""
        self.assertEqual(MOD.COMMON_ARGS[:4], ("-p", "kernel", "-p", "kernel-std"))

    def test_leg_environment_allow_list(self) -> None:
        """Keep approved keys, report only sorted dropped names, and set the cap."""
        kept = {
            "PATH": "/usr/bin",
            "RUSTFLAGS": "-D warnings",
            "CARGO_HOME": "/tmp/cargo",
            "CARGO_INCREMENTAL": "0",
            "CARGO_TERM_COLOR": "never",
            "CARGO_PROFILE_DEV_DEBUG": "0",
            "CARGO_HTTP_TIMEOUT": "30",
            "CARGO_NET_OFFLINE": "true",
            "CARGO_REGISTRIES_EXAMPLE_PROTOCOL": "sparse",
            "CARGO_REGISTRY_DEFAULT": "example",
        }
        dropped = (
            "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUNNER",
            "CARGO_MUTANTS_JOBS",
            "CARGO_ENCODED_RUSTFLAGS",
            "CARGO_BUILD_TARGET",
            "CARGO_ALIAS_MUTANTS",
            "CARGO_TARGET_DIR",
            "CARGO_SOURCE_EXAMPLE_REPLACE_WITH",
        )
        marker = "RHIZOMORPH_MUTANTS_AS_CAP"
        source = {**kept, **dict.fromkeys(dropped, "fixture-value"), marker: "1"}
        snapshot = dict(source)
        cleaned, _, err_txt = call_quiet(MOD.leg_environment, source)
        self.assertEqual(source, snapshot)
        self.assertEqual(cleaned, {**kept, marker: "4294967296"})
        self.assertEqual(len(err_txt.splitlines()), 1)
        self.assertEqual(
            err_txt.split(": ")[-1].strip(), ", ".join(map(repr, sorted(dropped)))
        )
        self.assertNotIn("fixture-value", err_txt)

    def test_leg_environment_adds_cap_to_empty_environment(self) -> None:
        """Set the same marker when it is absent and leave stderr quiet."""
        cleaned, _, err_txt = call_quiet(MOD.leg_environment, {})
        self.assertEqual(cleaned, {"RHIZOMORPH_MUTANTS_AS_CAP": "4294967296"})
        self.assertEqual(err_txt, "")

    def _invoke_gate_leg_capturing_dir(
        self, caught: int, unviable: int, leg_rc: int = 0
    ) -> tuple[int, str, Path]:
        """Run ``run_gate_leg`` with ``run_leg`` stubbed to populate ``--output``."""
        seen_dirs: list[Path] = []
        cwd_resolved = Path.cwd().resolve()

        def fake_run_leg(leg_name: str, leg_args: list[str], leg_timeout: int) -> int:
            """Validate private ``--output`` directory and write fixture counts."""
            self.assertEqual(leg_name, "gate")
            self.assertEqual(leg_timeout, MOD.GATE_TIMEOUT_SECONDS)
            out_idx = leg_args.index("--output")
            out_dir = Path(leg_args[out_idx + 1])
            self.assertTrue(out_dir.is_dir())
            out_resolved = out_dir.resolve()
            self.assertEqual(out_resolved.parent, Path(tempfile.gettempdir()).resolve())
            self.assertTrue(out_dir.name.startswith("mutants-gate-"))
            self.assertNotEqual(out_resolved, (cwd_resolved / "mutants.out").resolve())
            self.assertNotEqual(out_resolved, cwd_resolved)
            seen_dirs.append(out_dir)
            if leg_rc == 0:
                write_mutants_out(
                    out_dir,
                    {
                        "caught.txt": "caught\n" * caught,
                        "unviable.txt": "unviable\n" * unviable,
                    },
                )
            return leg_rc

        with mock.patch.object(MOD, "run_leg", side_effect=fake_run_leg):
            rc, _, err_txt = call_quiet(MOD.run_gate_leg)
        self.assertEqual(len(seen_dirs), 1)
        self.assertFalse(seen_dirs[0].exists())
        return rc, err_txt, seen_dirs[0]

    def test_gate_leg_uses_private_output_dir(self) -> None:
        """Read counts from a private temporary directory, a new one per run."""
        floor = MOD.GATE_CAUGHT_FLOOR
        pass_unviable = MOD.GATE_UNVIABLE_CEILING
        pass_caught = max(floor, MOD.GATE_MUTANTS_FLOOR - pass_unviable)
        dirs: list[Path] = []

        rc, err_txt, out_dir = self._invoke_gate_leg_capturing_dir(
            pass_caught, pass_unviable
        )
        self.assertEqual(rc, 0)
        self.assertEqual(err_txt, "")
        dirs.append(out_dir)

        rc, err_txt, out_dir = self._invoke_gate_leg_capturing_dir(
            floor - 1, pass_unviable
        )
        self.assertEqual(rc, 1)
        self.assertIn("caught mutants below the floor", err_txt)
        dirs.append(out_dir)

        rc, err_txt, out_dir = self._invoke_gate_leg_capturing_dir(
            pass_caught, pass_unviable, leg_rc=1
        )
        self.assertEqual(rc, 1)
        self.assertIn("gate leg failed", err_txt)
        dirs.append(out_dir)

        self.assertEqual(len(set(dirs)), 3)

    def test_gate_leg_private_dir_follows_tmpdir_inside_cwd(self) -> None:
        """Accept a ``tempfile`` directory inside cwd and still enforce gate counts."""
        floor = MOD.GATE_CAUGHT_FLOOR
        pass_unviable = MOD.GATE_UNVIABLE_CEILING
        pass_caught = max(floor, MOD.GATE_MUTANTS_FLOOR - pass_unviable)
        prev_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as raw_cwd:
            checkout = Path(raw_cwd).resolve()
            inside = checkout / "tmp-inside"
            inside.mkdir()
            inside_resolved = inside.resolve()
            os.chdir(checkout)
            try:
                with mock.patch.object(tempfile, "tempdir", str(inside)):
                    rc, err_txt, pass_dir = self._invoke_gate_leg_capturing_dir(
                        pass_caught, pass_unviable
                    )
                    self.assertEqual(rc, 0)
                    self.assertEqual(err_txt, "")
                    self.assertEqual(pass_dir.resolve().parent, inside_resolved)
                    self.assertFalse(pass_dir.exists())

                    rc, err_txt, fail_dir = self._invoke_gate_leg_capturing_dir(
                        floor - 1, pass_unviable
                    )
                    self.assertEqual(rc, 1)
                    self.assertIn("caught mutants below the floor", err_txt)
                    self.assertEqual(fail_dir.resolve().parent, inside_resolved)
                    self.assertFalse(fail_dir.exists())
            finally:
                os.chdir(prev_cwd)

    def test_gate_leg_ignores_stale_cwd_mutants_out(self) -> None:
        """Ignore a passing ``./mutants.out`` in cwd when private counts fail."""
        floor = MOD.GATE_CAUGHT_FLOOR
        pass_unviable = MOD.GATE_UNVIABLE_CEILING
        pass_caught = max(floor, MOD.GATE_MUTANTS_FLOOR - pass_unviable)
        prev_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as raw_cwd:
            cwd_dir = Path(raw_cwd).resolve()
            write_mutants_out(
                cwd_dir,
                {
                    "caught.txt": "caught\n" * pass_caught,
                    "unviable.txt": "unviable\n" * pass_unviable,
                },
            )
            os.chdir(cwd_dir)
            try:

                def fake_run_leg(_name: str, leg_args: list[str], _timeout: int) -> int:
                    """Write failing counts only when ``--output`` is outside cwd."""
                    out_dir = Path(leg_args[leg_args.index("--output") + 1])
                    if not out_dir.resolve().is_relative_to(cwd_dir):
                        write_mutants_out(
                            out_dir,
                            {
                                "caught.txt": "caught\n" * (floor - 1),
                                "unviable.txt": "unviable\n" * pass_unviable,
                            },
                        )
                    return 0

                with mock.patch.object(MOD, "run_leg", side_effect=fake_run_leg):
                    rc, _, err_txt = call_quiet(MOD.run_gate_leg)
            finally:
                os.chdir(prev_cwd)
        self.assertEqual(rc, 1)
        self.assertIn("caught mutants below the floor", err_txt)

    def test_run_leg_passes_sanitized_env_to_popen(self) -> None:
        """Start the leg subprocess at the repository root with a sanitized env."""
        MOD.CANCEL_SIGNALS.clear()
        fake_proc = mock.MagicMock()
        fake_proc.pid = 777
        fake_proc.wait.return_value = 0
        runner_key = "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUNNER"
        env_overrides = {
            "CARGO_MUTANTS_OUTPUT": "/tmp/override",
            "CARGO_MUTANTS_JOBS": "9",
            "MUTANTS_CHECK_KEEP": "present",
            runner_key: "test-runner-value",
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
        self.assertIn(runner_key, err_txt)
        self.assertEqual(mock_popen.call_args.kwargs.get("cwd"), MOD.REPO_ROOT)
        popen_env = mock_popen.call_args.kwargs["env"]
        self.assertNotIn("CARGO_MUTANTS_OUTPUT", popen_env)
        self.assertNotIn("CARGO_MUTANTS_JOBS", popen_env)
        self.assertNotIn(runner_key, popen_env)
        self.assertEqual(popen_env.get("MUTANTS_CHECK_KEEP"), "present")
        self.assertEqual(popen_env.get("RHIZOMORPH_MUTANTS_AS_CAP"), "4294967296")


class RepositoryCargoConfigTests(unittest.TestCase):
    """Replay repository-local Cargo config validation through ``load_config``."""

    def setUp(self) -> None:
        """Create a temporary Cargo directory with a valid mutation config."""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.cargo_dir = Path(tmp_dir.name) / ".cargo"
        self.cargo_dir.mkdir()
        self.mutants_config = self.cargo_dir / "mutants.toml"
        self.mutants_config.write_text(
            CAPPED_CARGO_ARGS + 'exclude_re = ["ok$"]\n', encoding="utf-8"
        )

    def assert_config_rejected(self, path: Path, message: str) -> None:
        """Require status 2 and a diagnostic naming the offending file."""
        (cfg, status), _, err_txt = call_quiet(MOD.load_config, self.mutants_config)
        self.assertEqual(status, 2)
        self.assertIsNone(cfg)
        self.assertIn(str(path), err_txt)
        self.assertIn(message, err_txt)

    def assert_config_accepted(self) -> None:
        """Require successful validation with no diagnostics."""
        (cfg, status), _, err_txt = call_quiet(MOD.load_config, self.mutants_config)
        self.assertEqual(status, 0, err_txt)
        self.assertIsInstance(cfg, MOD.MutantsConfig)
        self.assertEqual(err_txt, "")

    def test_missing_cargo_config_passes(self) -> None:
        """Accept a checkout with neither Cargo config filename."""
        self.assert_config_accepted()

    def test_dangling_cargo_config_passes(self) -> None:
        """Treat a dangling Cargo config symlink as absent."""
        (self.cargo_dir / "config.toml").symlink_to("missing.toml")
        self.assert_config_accepted()

    def test_cargo_config_accepts_term_and_profile(self) -> None:
        """Accept unrelated Cargo configuration namespaces."""
        (self.cargo_dir / "config.toml").write_text(
            '[term]\ncolor = "never"\n[profile.dev]\ndebug = 0\n', encoding="utf-8"
        )
        self.assert_config_accepted()

    def test_cargo_config_rejects_sorted_keys(self) -> None:
        """Refuse a config that could change how Cargo invokes the tests."""
        path = self.cargo_dir / "config.toml"
        path.write_text(
            '[unstable]\nfoo = true\n[build]\ntarget = "x"\n[alias]\nmutants = "test"\n',
            encoding="utf-8",
        )
        self.assert_config_rejected(path, "alias, build, unstable")

    def test_cargo_config_rejects_includes(self) -> None:
        """Refuse both include forms and check the legacy config for includes."""
        cases = (
            ("config.toml", '[[include]]\npath = "extra.toml"\n'),
            ("config.toml", 'include = "extra.toml"\n'),
            ("config", '[[include]]\npath = "extra.toml"\n'),
        )
        for idx in range(len(cases)):
            filename, content = cases[idx]
            path = self.cargo_dir / filename
            with self.subTest(filename=filename, content=content):
                path.write_text(content, encoding="utf-8")
                self.assert_config_rejected(path, "include")
            path.unlink()

    def test_cargo_config_rejects_path_env(self) -> None:
        """Refuse both table and string PATH settings in Cargo's environment."""
        cases = ('{ value = "/tools", force = true }', '"/tools"')
        path = self.cargo_dir / "config.toml"
        for idx in range(len(cases)):
            value = cases[idx]
            with self.subTest(value=value):
                path.write_text(f"[env]\nPATH = {value}\n", encoding="utf-8")
                self.assert_config_rejected(path, "env")

    def test_cargo_config_rejects_unrelated_env_key(self) -> None:
        """Refuse environment tables even when they leave PATH alone."""
        cases = ('"info"', "1")
        path = self.cargo_dir / "config.toml"
        for idx in range(len(cases)):
            value = cases[idx]
            with self.subTest(value=value):
                path.write_text(f"[env]\nRUST_LOG = {value}\n", encoding="utf-8")
                self.assert_config_rejected(path, "env")

    def test_cargo_config_rejects_malformed_tables(self) -> None:
        """Refuse scalar values in place of environment and target tables."""
        cases = (
            ('env = "x"\n', "env"),
            ('target = "x"\n', "target"),
            ("[target]\nfoo = 1\n", "target"),
        )
        path = self.cargo_dir / "config.toml"
        for idx in range(len(cases)):
            content, key = cases[idx]
            with self.subTest(key=key):
                path.write_text(content, encoding="utf-8")
                self.assert_config_rejected(path, key)

    def test_cargo_config_rejects_target_triple_and_cfg_runners(self) -> None:
        """Reject both forms of Cargo target runner."""
        cases = (
            (
                "x86_64-unknown-linux-gnu",
                '[target.x86_64-unknown-linux-gnu]\nrunner = ["env"]\n',
            ),
            ("cfg(unix)", "[target.'cfg(unix)']\nrunner = \"env\"\n"),
        )
        path = self.cargo_dir / "config.toml"
        for idx in range(len(cases)):
            target, content = cases[idx]
            with self.subTest(target=target):
                path.write_text(content, encoding="utf-8")
                self.assert_config_rejected(path, "target")

    def test_cargo_config_rejects_legacy_filename(self) -> None:
        """Check the legacy file even when a benign config.toml also exists."""
        (self.cargo_dir / "config.toml").write_text("[term]\n", encoding="utf-8")
        path = self.cargo_dir / "config"
        path.write_text(
            '[target.x86_64-unknown-linux-gnu]\nrunner = ["env"]\n', encoding="utf-8"
        )
        self.assert_config_rejected(path, "target")

    def test_cargo_config_rejects_invalid_toml(self) -> None:
        """Fail closed on invalid syntax or encoding."""
        path = self.cargo_dir / "config.toml"
        path.write_text("[target\n", encoding="utf-8")
        self.assert_config_rejected(path, "failed to read")
        path.write_bytes(b"\xff")
        self.assert_config_rejected(path, "failed to read")

    def test_cargo_config_rejects_directory(self) -> None:
        """Fail closed when the config path is a directory."""
        path = self.cargo_dir / "config.toml"
        path.mkdir()
        self.assert_config_rejected(path, "not a regular file")

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux FIFOs")
    def test_config_fifos_are_rejected_without_a_writer(self) -> None:
        """Refuse either config FIFO without waiting for a writer."""

        def fifo_open_timed_out(_signum: int, _frame: object) -> None:
            """Fail the fixture if opening the FIFO blocks."""
            raise AssertionError("blocked opening a config FIFO without a writer")

        previous = signal.signal(signal.SIGALRM, fifo_open_timed_out)
        self.addCleanup(signal.signal, signal.SIGALRM, previous)
        self.addCleanup(signal.alarm, 0)
        cargo_config = self.cargo_dir / "config.toml"
        with self.subTest(path=cargo_config):
            os.mkfifo(cargo_config, 0o600)
            signal.alarm(2)
            ok, _, err_txt = call_quiet(MOD.check_cargo_config, cargo_config)
            signal.alarm(0)
            self.assertFalse(ok)
            self.assertIn(str(cargo_config), err_txt)
            self.assertIn("not a regular file", err_txt)
        with self.subTest(path=self.mutants_config):
            self.mutants_config.unlink()
            os.mkfifo(self.mutants_config, 0o600)
            signal.alarm(2)
            self.assert_config_rejected(self.mutants_config, "not a regular file")
            signal.alarm(0)

    def test_mutants_config_rejects_invalid_utf8(self) -> None:
        """Report unreadable UTF-8 in mutants.toml as a configuration error."""
        self.mutants_config.write_bytes(b"\xff")
        self.assert_config_rejected(self.mutants_config, "failed to read")


class AddressSpaceSkipReasonTests(unittest.TestCase):
    """Check Cargo canary limit compatibility without reading process limits."""

    def test_compatible_limits(self) -> None:
        """Accept infinity, reachable hard limits, and distinguishable soft limits."""
        cap = MOD.TEST_RUNNER_CAP_BYTES
        infinity = -1
        cases = (
            (infinity, infinity, True),
            (cap, infinity, False),
            (cap + 1, infinity, True),
            (cap - 1, cap, True),
            (cap - 1, infinity, True),
        )
        for soft, hard, needs_distinct_soft in cases:
            with self.subTest(
                soft=soft, hard=hard, needs_distinct_soft=needs_distinct_soft
            ):
                self.assertIsNone(
                    address_space_skip_reason(
                        soft,
                        hard,
                        cap,
                        infinity=infinity,
                        needs_distinct_soft=needs_distinct_soft,
                    )
                )

    def test_matching_soft_limit_requires_skip_for_home_runner(self) -> None:
        """Reject a soft limit that masks a runner skipping the cap."""
        cap = MOD.TEST_RUNNER_CAP_BYTES
        infinity = -1
        reason = address_space_skip_reason(
            cap, infinity, cap, infinity=infinity, needs_distinct_soft=True
        )
        self.assertIn("inherited soft RLIMIT_AS", reason or "")

    def test_hard_limit_below_cap_requires_skip_for_both_runners(self) -> None:
        """Reject a finite hard limit below the requested cap for both runners."""
        cap = MOD.TEST_RUNNER_CAP_BYTES
        for needs_distinct_soft in (False, True):
            with self.subTest(needs_distinct_soft=needs_distinct_soft):
                reason = address_space_skip_reason(
                    cap - 1,
                    cap - 1,
                    cap,
                    infinity=-1,
                    needs_distinct_soft=needs_distinct_soft,
                )
                self.assertIn("inherited hard RLIMIT_AS", reason or "")


@unittest.skipUnless(
    sys.platform.startswith("linux")
    and all(shutil.which(tool) for tool in ("cargo", "rustc", "prlimit")),
    "requires Linux with cargo, rustc, and prlimit on PATH",
)
class CargoRunnerCapTests(unittest.TestCase):
    """Check the mutation cap canary against Cargo home runner configuration."""

    def setUp(self) -> None:
        """Use a fresh Cargo home and keep build artifacts in the ignored target tree."""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.cargo_home = Path(tmp_dir.name)
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("CARGO_", "GIT_"))
            and key != "RHIZOMORPH_MUTANTS_AS_CAP"
        }
        self.env.update(
            CARGO_HOME=tmp_dir.name,
            CARGO_NET_OFFLINE="true",
            CARGO_TARGET_DIR=str(MOD.REPO_ROOT / "target" / "mutants-cap-fixture"),
        )

    def run_canary(self, *, mutation_leg: bool) -> subprocess.CompletedProcess[str]:
        """Build and run only the shared canary, optionally with the mutation cap."""
        env = self.env.copy()
        args = ["cargo", "test", "--locked", "-p", "kernel", "--test", "mutants_cap"]
        if mutation_leg:
            env["RHIZOMORPH_MUTANTS_AS_CAP"] = str(MOD.TEST_RUNNER_CAP_BYTES)
            args.append(MOD.TEST_RUNNER_CAP_ARG)
        args.extend(("--", "mutation_runner_sets_address_space_cap"))
        return subprocess.run(
            args,
            cwd=MOD.REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=600,
            check=False,
        )

    def test_home_runner_cannot_clear_cap_canary(self) -> None:
        """Reject a host runner that skips the cap and clears the test environment."""
        skip_for_inherited_limits(self, needs_distinct_soft=True)
        version = subprocess.run(
            ["rustc", "-vV"],
            cwd=MOD.REPO_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        host = version.stdout.partition("\nhost: ")[2].partition("\n")[0]
        self.assertTrue(host, version.stdout)
        (self.cargo_home / "config.toml").write_text(
            f'[target.{host}]\nrunner = ["env", "-i"]\n', encoding="utf-8"
        )
        result = self.run_canary(mutation_leg=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("mutation_runner_sets_address_space_cap", result.stdout)
        self.assertIn("mutation test binary must inherit RLIMIT_AS", result.stdout)

    def test_mutation_leg_with_cap_runner_passes(self) -> None:
        """Accept the configured prlimit runner when it applies the requested cap."""
        skip_for_inherited_limits(self, needs_distinct_soft=False)
        result = self.run_canary(mutation_leg=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "test mutation_runner_sets_address_space_cap ... ok", result.stdout
        )

    def test_unmarked_build_without_cap_passes(self) -> None:
        """Allow plain Cargo tests without the mutation marker or runner cap."""
        result = self.run_canary(mutation_leg=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "test mutation_runner_sets_address_space_cap ... ok", result.stdout
        )


class PrlimitTests(unittest.TestCase):
    """Verify the executable on the leg's PATH enforces the cap."""

    def test_real_prlimit_sets_cap(self) -> None:
        """Accept util-linux prlimit when the Python child sees 4 GiB."""
        prlimit = shutil.which("prlimit")
        if not sys.platform.startswith("linux") or prlimit is None:
            self.skipTest("requires Linux util-linux prlimit")
        skip_for_inherited_limits(self, needs_distinct_soft=False)
        env = {"PATH": f"{Path(prlimit).absolute().parent}{os.pathsep}{os.defpath}"}
        ok, _, err_txt = call_quiet(MOD.check_prlimit, env)
        self.assertTrue(ok, err_txt)
        self.assertEqual(err_txt, "")

    @unittest.skipUnless(
        sys.platform.startswith("linux") and shutil.which("prlimit") is not None,
        "requires Linux util-linux prlimit",
    )
    def test_fake_prlimit_forwards_without_setting_cap(self) -> None:
        """Reject a PATH shim that execs the Python child without a limit."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            shim = Path(tmp_dir) / "prlimit"
            shim.write_text('#!/bin/sh\nshift\nexec "$@"\n', encoding="utf-8")
            shim.chmod(0o755)
            env = {"PATH": f"{tmp_dir}{os.pathsep}{os.defpath}"}
            with temporary_address_space_limit(MOD.TEST_RUNNER_CAP_BYTES - 4096):
                ok, _, err_txt = call_quiet(MOD.check_prlimit, env)
        self.assertFalse(ok)
        self.assertIn("prlimit preflight", err_txt)
        self.assertIn("RLIMIT_AS", err_txt)

    def test_prlimit_missing_from_path(self) -> None:
        """Reject a PATH without prlimit."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ok, _, err_txt = call_quiet(MOD.check_prlimit, {"PATH": tmp_dir})
        self.assertFalse(ok)
        self.assertIn("prlimit preflight", err_txt)

    def test_prlimit_uses_leg_environment_and_deadline(self) -> None:
        """Pin the preflight argv, deadline, and session subprocess options."""
        env = {"MUTANTS_CHECK_SENTINEL": "present"}
        cmd = [
            "prlimit",
            "--as=4294967296",
            sys.executable,
            "-I",
            "-c",
            "import resource; print(resource.getrlimit(resource.RLIMIT_AS)[0])",
        ]
        proc = mock.Mock(pid=777)

        def start(*_args: object, stdout: BinaryIO, **_kwargs: object) -> mock.Mock:
            """Write the child output to the provided temporary file."""
            self.assertGreaterEqual(stdout.fileno(), 0)
            stdout.write(b"4294967296\n")
            return proc

        with (
            mock.patch.object(MOD, "run_session", wraps=MOD.run_session) as session,
            mock.patch.object(MOD.subprocess, "Popen", side_effect=start) as popen,
            mock.patch.object(MOD, "wait_exited", return_value=True),
            mock.patch.object(MOD, "reap_exited_leg", return_value=0),
        ):
            self.assertTrue(MOD.check_prlimit(env))
        stdout = popen.call_args.kwargs["stdout"]
        self.assertTrue(stdout.closed)
        self.assertEqual(MOD.PRLIMIT_PREFLIGHT_SECONDS, 30)
        session.assert_called_once_with(
            "prlimit preflight", cmd, 30, env, stdout=stdout
        )
        popen.assert_called_once_with(
            cmd,
            start_new_session=True,
            env=env,
            cwd=MOD.REPO_ROOT,
            stdout=stdout,
        )

    def test_prlimit_requires_cap_and_verified_success(self) -> None:
        """Require the exact cap, a successful exit, and verified cleanup."""
        cases = (
            (0, b"4294967295\n", "did not report the expected RLIMIT_AS"),
            (1, b"4294967296\n", "failed with exit 1"),
            (None, b"4294967296\n", "failed to complete with verified cleanup"),
        )
        for idx in range(len(cases)):
            rc, output, message = cases[idx]
            with (
                self.subTest(rc=rc, output=output),
                mock.patch.object(
                    MOD.tempfile, "TemporaryFile", return_value=io.BytesIO(output)
                ),
                mock.patch.object(MOD, "run_session", return_value=rc),
            ):
                ok, _, err_txt = call_quiet(MOD.check_prlimit, {})
            self.assertFalse(ok)
            self.assertIn("prlimit preflight", err_txt)
            self.assertIn(message, err_txt)

    def test_prlimit_rejects_oversized_output(self) -> None:
        """Reject 100,000 bytes even when the output starts with the expected cap."""
        cap = str(MOD.TEST_RUNNER_CAP_BYTES).encode("ascii")
        output = io.BytesIO(cap.ljust(100_000, b" "))
        with (
            mock.patch.object(output, "read", wraps=output.read) as read,
            mock.patch.object(MOD.tempfile, "TemporaryFile", return_value=output),
            mock.patch.object(MOD, "run_session", return_value=0),
        ):
            ok, _, err_txt = call_quiet(MOD.check_prlimit, {})
        read.assert_called_once_with(64)
        self.assertFalse(ok)
        self.assertIn("did not report the expected RLIMIT_AS", err_txt)

    def test_main_enables_subreaper_before_preflight(self) -> None:
        """Enable subreaping, pass the leg environment, and stop on preflight failure."""
        config = MOD.MutantsConfig([], [], False)
        env = {"PATH": os.defpath, "RHIZOMORPH_MUTANTS_AS_CAP": "4294967296"}
        startup = mock.Mock()
        with (
            mock.patch.object(signal, "signal"),
            mock.patch.object(MOD, "load_config", return_value=(config, 0)) as load,
            mock.patch.object(MOD, "leg_environment", return_value=env) as mock_env,
            mock.patch.object(MOD, "check_prlimit", return_value=False) as preflight,
            mock.patch.object(MOD, "enable_subreaper", return_value=True) as subreaper,
            mock.patch.object(MOD, "run_gate_leg", return_value=0) as gate,
            mock.patch.object(MOD, "run_planted_leg", return_value=0) as planted,
        ):
            startup.attach_mock(load, "load")
            startup.attach_mock(subreaper, "subreaper")
            startup.attach_mock(preflight, "preflight")
            rc, _, _ = call_quiet(MOD.main)
        self.assertEqual(rc, 2)
        mock_env.assert_called_once_with(os.environ)
        self.assertEqual(
            startup.mock_calls,
            [
                mock.call.load(MOD.CONFIG_PATH),
                mock.call.subreaper(),
                mock.call.preflight(env),
            ],
        )
        gate.assert_not_called()
        planted.assert_not_called()


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
            mock.patch.object(MOD, "check_prlimit", return_value=True) as preflight,
            mock.patch.object(MOD, "enable_subreaper", return_value=False),
            mock.patch.object(MOD, "run_gate_leg") as mock_gate,
        ):
            rc, _, _ = call_quiet(MOD.main)
        self.assertEqual(rc, 1)
        self.assertFalse(preflight.called, "preflight ran without a subreaper")
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

    def test_stop_leg_waits_and_reaps_when_post_kill_probe_misses(self) -> None:
        """Continue to ``proc.wait`` and ``reap_orphans`` after a missed kill probe."""
        events: list[str] = []
        fake_proc = mock.MagicMock()
        fake_proc.pid = 702

        def rec_wait(*_args: object, **_kwargs: object) -> int:
            """Record ``proc.wait`` in ``events``."""
            events.append("wait")
            return 0

        def rec_orphans(_leg: str) -> bool:
            """Record ``reap_orphans`` in ``events`` and return ``True``."""
            events.append("orphans")
            return True

        fake_proc.wait.side_effect = rec_wait
        with (
            mock.patch.object(MOD, "signal_leg"),
            mock.patch.object(MOD, "wait_exited", return_value=False),
            mock.patch.object(MOD, "kill_session_leftovers", return_value=True),
            mock.patch.object(MOD, "reap_orphans", side_effect=rec_orphans),
        ):
            _, _, err_txt = call_quiet(MOD.stop_leg, "gate", fake_proc)
        self.assertEqual(events, ["wait", "orphans"])
        self.assertIn("did not exit after kill", err_txt)
        self.assertNotIn("not reaped", err_txt)

        fake_proc.wait.side_effect = subprocess.TimeoutExpired(["cargo"], 1)
        with (
            mock.patch.object(MOD, "signal_leg"),
            mock.patch.object(MOD, "wait_exited", return_value=False),
            mock.patch.object(MOD, "kill_session_leftovers", return_value=True),
            mock.patch.object(MOD, "reap_orphans") as mock_orphans,
        ):
            _, _, err_txt = call_quiet(MOD.stop_leg, "gate", fake_proc)
        mock_orphans.assert_not_called()
        self.assertIn("did not exit after kill", err_txt)
        self.assertIn("not reaped after kill", err_txt)


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

    def test_main_honours_cancel_when_preflight_fails(self) -> None:
        """Prefer a cancellation exit over the preflight failure exit."""
        config = MOD.MutantsConfig([], [], False)
        MOD.CANCEL_SIGNALS.append(int(signal.SIGTERM))
        with (
            mock.patch.object(signal, "signal"),
            mock.patch.object(MOD, "load_config", return_value=(config, 0)),
            mock.patch.object(MOD, "check_prlimit", return_value=False),
            mock.patch.object(MOD, "enable_subreaper", return_value=True) as subreaper,
            mock.patch.object(MOD, "run_gate_leg") as gate,
        ):
            rc, _, err_txt = call_quiet(MOD.main)
        self.assertEqual(rc, MOD.SIGNAL_EXIT_BASE + int(signal.SIGTERM))
        self.assertIn("cancelled by SIGTERM", err_txt)
        subreaper.assert_called_once_with()
        gate.assert_not_called()

    def test_main_catches_preflight_cancellation(self) -> None:
        """Report a session cancellation from preflight and skip both legs."""
        config = MOD.MutantsConfig([], [], False)
        signum = int(signal.SIGTERM)
        with (
            mock.patch.object(signal, "signal"),
            mock.patch.object(MOD, "load_config", return_value=(config, 0)),
            mock.patch.object(MOD, "enable_subreaper", return_value=True),
            mock.patch.object(
                MOD, "check_prlimit", side_effect=MOD.LegCancelled(signum)
            ),
            mock.patch.object(MOD, "run_gate_leg") as gate,
            mock.patch.object(MOD, "run_planted_leg") as planted,
        ):
            rc, _, err_txt = call_quiet(MOD.main)
        self.assertEqual(rc, MOD.SIGNAL_EXIT_BASE + signum)
        self.assertIn("cancelled by SIGTERM", err_txt)
        gate.assert_not_called()
        planted.assert_not_called()

    def test_main_honours_late_cancel_after_legs(self) -> None:
        """Return ``128 + signum`` if a signal arrives after ``run_leg`` returns."""
        compiled, _, _ = call_quiet(MOD.compile_exclusions, ["pat$"], Path("fixture"))
        cfg = MOD.MutantsConfig(compiled or [], [], True)

        def cancel_in_planted(_cfg: object) -> int:
            """Simulate ``SIGTERM`` arriving during planted-leg verification."""
            MOD.CANCEL_SIGNALS.append(int(signal.SIGTERM))
            return 0

        def cancel_in_gate() -> int:
            """Simulate ``SIGINT`` arriving after ``run_leg`` in ``run_gate_leg``."""
            MOD.CANCEL_SIGNALS.append(int(signal.SIGINT))
            return 1

        with (
            mock.patch.object(signal, "signal"),
            mock.patch.object(MOD, "load_config", return_value=(cfg, 0)),
            mock.patch.object(MOD, "check_prlimit", return_value=True),
            mock.patch.object(MOD, "enable_subreaper", return_value=True),
            mock.patch.object(MOD, "run_gate_leg", return_value=0) as gate,
            mock.patch.object(
                MOD, "run_planted_leg", side_effect=cancel_in_planted
            ) as planted,
        ):
            rc, _, err_txt = call_quiet(MOD.main)
            self.assertEqual(rc, MOD.SIGNAL_EXIT_BASE + int(signal.SIGTERM))
            self.assertIn("cancelled by SIGTERM", err_txt)

            MOD.CANCEL_SIGNALS.clear()
            gate.side_effect = cancel_in_gate
            planted.reset_mock()
            rc, _, err_txt = call_quiet(MOD.main)
            self.assertEqual(rc, MOD.SIGNAL_EXIT_BASE + int(signal.SIGINT))
            self.assertIn("cancelled by SIGINT", err_txt)
            planted.assert_not_called()

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
    sys.platform.startswith("linux")
    and hasattr(os, "pidfd_open")
    and hasattr(os, "P_PIDFD"),
    "requires Linux pidfd waitid support",
)
class LeftoverPidCleanupTests(unittest.TestCase):
    """Replay live-child, non-child, and zombie cases for ``_kill_leftover_pid``."""

    def test_kills_live_child(self) -> None:
        """Kill a live child process and reap its ``SIGKILL`` exit status."""
        proc = subprocess.Popen(["sleep", "30"])
        try:
            RealDescendantCleanupTests._kill_leftover_pid(proc.pid)
            rc = proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                MOD.signal_leg(proc, signal.SIGKILL)
                proc.wait(timeout=5)
        self.assertEqual(rc, -int(signal.SIGKILL))

    def test_skips_non_child_parent_pid(self) -> None:
        """Refuse to signal ``os.getppid()`` when ``waitid`` rejects ownership."""
        parent_pid = os.getppid()
        self.assertGreater(parent_pid, 1)
        with mock.patch.object(signal, "pidfd_send_signal", create=True) as mock_send:
            RealDescendantCleanupTests._kill_leftover_pid(parent_pid)
        mock_send.assert_not_called()

    def test_skips_exited_unreaped_child_without_reaping(self) -> None:
        """Leave an exited zombie child unsignalled and still waitable."""
        proc = subprocess.Popen(["sleep", "30"])
        try:
            MOD.signal_leg(proc, signal.SIGKILL)
            self.assertTrue(MOD.wait_exited(proc.pid, 5.0))
            with mock.patch.object(
                signal, "pidfd_send_signal", create=True
            ) as mock_send:
                RealDescendantCleanupTests._kill_leftover_pid(proc.pid)
            mock_send.assert_not_called()
            probe = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            self.assertIsNotNone(probe)
            rc = proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                MOD.signal_leg(proc, signal.SIGKILL)
                proc.wait(timeout=5)
        self.assertEqual(rc, -int(signal.SIGKILL))


@unittest.skipUnless(
    sys.platform.startswith("linux") and hasattr(os, "pidfd_open"),
    "requires Linux pidfd support",
)
class RealDescendantCleanupTests(unittest.TestCase):
    """Exercise live descendant cleanup on timeout and immediate exit paths."""

    def setUp(self) -> None:
        """Create temporary stub/FIFO fixtures and enable child subreaper."""
        MOD.CANCEL_SIGNALS.clear()
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="mutants descendant $USER '-")
        self.base = Path(self.tmp_dir.name)
        self.fifo_path = self.base / "grandchild.fifo"
        self.ready_path = self.base / "ready.fifo"
        self.pid_file = self.base / "grandchild.pid"
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

    @staticmethod
    def _kill_leftover_pid(pid: int) -> None:
        """Pin identity via pidfd and prove ownership with waitid before SIGKILL."""
        if pid <= 1:
            return
        try:
            fd = os.pidfd_open(pid)
        except OSError:
            return
        try:
            try:
                exited = os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except OSError:
                return
            if exited is None:
                with contextlib.suppress(OSError):
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
        finally:
            with contextlib.suppress(OSError):
                os.close(fd)

    def _write_process_stub(
        self, executable: str, launcher_prefix: str, tail_cmd: str
    ) -> None:
        """Write a shell stub spawning a FIFO-holding child."""
        quoted_pid = shlex.quote(str(self.pid_file))
        quoted_fifo = shlex.quote(str(self.fifo_path))
        quoted_ready = shlex.quote(str(self.ready_path))
        script = (
            "#!/bin/sh\n"
            f"{launcher_prefix} sh -c '\n"
            '  printf "%s\\n" "$$" > "$1"\n'
            '  exec 3>"$2"\n'
            '  printf "x" >&3\n'
            '  printf "r\\n" > "$3"\n'
            "  exec sleep 60\n"
            f"' sh {quoted_pid} {quoted_fifo} {quoted_ready} "
            "</dev/null >/dev/null 2>&1 &\n"
            f"read -r _ < {quoted_ready}\n"
            f"{tail_cmd}\n"
        )
        stub_path = self.base / executable
        stub_path.write_text(script, encoding="utf-8")
        stub_path.chmod(0o755)

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
        self._write_process_stub("cargo", "", "exec sleep 60")
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
        self._write_process_stub("cargo", "setsid", "exit 0")
        prepended_path = f"{self.base}{os.pathsep}{os.environ.get('PATH', '')}"
        with mock.patch.dict(os.environ, {"PATH": prepended_path}):
            rc, _, err_txt = call_quiet(MOD.run_leg, "gate", [], 5)
        self.assertEqual(rc, 0)
        self.assertEqual(err_txt, "")
        self._assert_fifo_byte_then_eof()

    def _assert_descendant_reaped(self) -> None:
        """Verify the recorded child PID is gone and its FIFO has reached EOF."""
        pid = int(self.pid_file.read_text(encoding="utf-8"))
        self.assertFalse(Path(f"/proc/{pid}").exists(), f"descendant {pid} remains")
        self._assert_fifo_byte_then_eof()

    def test_prlimit_timeout_reaps_descendant(self) -> None:
        """Reject a timed-out prlimit and reap its background child before return."""
        self._write_process_stub("prlimit", "", "exec sleep 4")
        env = {"PATH": f"{self.base}{os.pathsep}{os.defpath}"}
        with (
            mock.patch.object(MOD, "PRLIMIT_PREFLIGHT_SECONDS", 2),
            mock.patch.object(MOD, "TERMINATE_GRACE_SECONDS", 1),
        ):
            ok, _, err_txt = call_quiet(MOD.check_prlimit, env)
        self._assert_descendant_reaped()
        self.assertFalse(ok)
        self.assertIn("prlimit preflight failed", err_txt)
        self.assertIn("exceeded its 2s deadline", err_txt)

    def test_prlimit_success_reaps_setsid_orphan(self) -> None:
        """Accept the printed cap after reaping an orphan in a separate session."""
        self._write_process_stub(
            "prlimit", "setsid", f"printf '%s\\n' {MOD.TEST_RUNNER_CAP_BYTES}\nexit 0"
        )
        env = {"PATH": f"{self.base}{os.pathsep}{os.defpath}"}
        ok, _, err_txt = call_quiet(MOD.check_prlimit, env)
        self._assert_descendant_reaped()
        self.assertTrue(ok, err_txt)


if __name__ == "__main__":
    unittest.main()
