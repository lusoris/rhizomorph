// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Verify the address-space limit inherited by mutation tests.

/// Read the soft address-space limit, distinguishing unlimited from invalid input.
#[allow(
    clippy::option_option,
    reason = "None means a missing Max address space line or invalid value, Some(None) means unlimited, and Some(Some(n)) holds the finite byte count"
)]
fn soft_address_space_limit(text: &str) -> Option<Option<u64>> {
    for line in text.lines() {
        let Some(fields) = line
            .strip_prefix("Max address space")
            .and_then(|rest| rest.strip_prefix(char::is_whitespace))
        else {
            continue;
        };
        let soft = fields.split_ascii_whitespace().next()?;
        return if soft == "unlimited" {
            Some(None)
        } else {
            soft.parse().ok().map(Some)
        };
    }
    None
}

/// Fail if the mutation leg's requested cap did not reach this test binary.
#[test]
#[allow(
    clippy::assertions_on_constants,
    reason = "Only mutation legs require Linux"
)]
fn mutation_runner_sets_address_space_cap() {
    let Some(marker) = std::env::var_os("RHIZOMORPH_MUTANTS_AS_CAP") else {
        return;
    };
    let cap = marker
        .to_str()
        .filter(|value| value.bytes().all(|byte| byte.is_ascii_digit()))
        .and_then(|value| value.parse::<u64>().ok())
        .expect("RHIZOMORPH_MUTANTS_AS_CAP must be a decimal byte count");
    assert!(
        cfg!(target_os = "linux"),
        "the prlimit runner does not apply to a non-Linux target"
    );
    let limits = std::fs::read_to_string("/proc/self/limits")
        .expect("failed to read /proc/self/limits for the mutation runner cap");
    assert_eq!(
        soft_address_space_limit(&limits),
        Some(Some(cap)),
        "mutation test binary must inherit RLIMIT_AS of {cap} bytes"
    );
}

/// Parse the soft value from a capped `/proc/self/limits` row.
#[test]
fn parses_capped_address_space() {
    assert_eq!(
        soft_address_space_limit(
            "Max address space         4294967296           4294967296           bytes\n"
        ),
        Some(Some(4_294_967_296))
    );
}

/// Distinguish unlimited, missing, and invalid soft values.
#[test]
fn distinguishes_unlimited_and_invalid_address_space() {
    assert_eq!(
        soft_address_space_limit(
            "Max address space         unlimited            unlimited            bytes\n"
        ),
        Some(None)
    );
    assert_eq!(
        soft_address_space_limit("Max stack size 8192 8192 bytes\n"),
        None
    );
    assert_eq!(
        soft_address_space_limit("Max address space garbage 4294967296 bytes\n"),
        None
    );
}

/// Preserve both a value one byte below the cap and the minimum value.
#[test]
fn parses_address_space_boundaries() {
    assert_eq!(
        soft_address_space_limit("Max address space 4294967295 4294967296 bytes\n"),
        Some(Some(4_294_967_295))
    );
    assert_eq!(
        soft_address_space_limit("Max address space 0 0 bytes\n"),
        Some(Some(0))
    );
}
