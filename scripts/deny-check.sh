#!/bin/sh
# SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
# SPDX-License-Identifier: EUPL-1.2

set -eu

if ! cargo deny --manifest-path Cargo.toml check licenses; then
    echo "deny-check: workspace leg failed (expected exit 0)" >&2
    exit 1
fi

if cargo deny --manifest-path tests/deny-planted/Cargo.toml --config deny.toml check licenses; then
    echo "deny-check: planted negative leg succeeded unexpectedly (expected non-zero exit)" >&2
    exit 1
fi
