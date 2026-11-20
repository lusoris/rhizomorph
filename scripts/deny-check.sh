#!/bin/sh
# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2

set -eu

seconds=${DENY_CHECK_DEADLINE-300}
case $seconds in
    '' | 0* | *[!0-9]* | ?????*) seconds=0 ;;
esac
if [ "$seconds" -lt 1 ] || [ "$seconds" -gt 3600 ]; then
    echo "deny-check: DENY_CHECK_DEADLINE must be a whole number of seconds from 1 to 3600 without leading zeros, got '${DENY_CHECK_DEADLINE-}'" >&2
    exit 2
fi

if command -v timeout >/dev/null 2>&1; then
    deadline=timeout
elif command -v gtimeout >/dev/null 2>&1; then
    deadline=gtimeout
else
    echo "deny-check: neither timeout nor gtimeout is available" >&2
    exit 2
fi

output=$(mktemp)
trap 'rm -f "$output"' EXIT HUP INT TERM
status=0
"$deadline" -k 10 "$seconds" cargo deny --manifest-path Cargo.toml check licenses || status=$?
if [ "$status" -ne 0 ]; then
    case $status in
        124 | 137) echo "deny-check: workspace leg exceeded its ${seconds}s deadline (exit $status)" >&2 ;;
        *) echo "deny-check: workspace leg failed (exit $status)" >&2 ;;
    esac
    exit 1
fi

status=0
"$deadline" -k 10 "$seconds" cargo deny --manifest-path tests/deny-planted/Cargo.toml --config deny.toml check licenses >"$output" 2>&1 || status=$?
cat "$output"
if [ "$status" -ge 124 ]; then
    case $status in
        124 | 137) echo "deny-check: planted leg exceeded its ${seconds}s deadline (exit $status)" >&2 ;;
        *) echo "deny-check: planted leg did not finish cargo-deny (exit $status)" >&2 ;;
    esac
    exit 1
fi
if [ "$status" -eq 0 ] || ! grep -Fq 'planted-gpl' "$output" ||
    ! grep -Fq 'GPL-3.0-only' "$output" || ! grep -Fq 'error[rejected]' "$output"; then
    echo "deny-check: planted leg did not report the expected licence rejection (exit $status)" >&2
    exit 1
fi
