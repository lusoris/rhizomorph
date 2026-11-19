#!/bin/sh
# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2

set -eu

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
seconds=${DENY_CHECK_DEADLINE:-300}
status=0
"$deadline" "$seconds" cargo deny --manifest-path Cargo.toml check licenses || status=$?
if [ "$status" -ne 0 ]; then
    echo "deny-check: workspace leg failed (exit $status)" >&2
    exit 1
fi

status=0
"$deadline" "$seconds" cargo deny --manifest-path tests/deny-planted/Cargo.toml --config deny.toml check licenses >"$output" 2>&1 || status=$?
cat "$output"
if [ "$status" -eq 124 ]; then
    echo "deny-check: planted leg timed out (exit 124)" >&2
    exit 1
fi
if [ "$status" -eq 0 ] || ! grep -Fq 'planted-gpl' "$output" ||
    ! grep -Fq 'GPL-3.0-only' "$output" || ! grep -Fq 'error[rejected]' "$output"; then
    echo "deny-check: planted leg did not report the expected licence rejection (exit $status)" >&2
    exit 1
fi
