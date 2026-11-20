// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Planted negative fixture dependency for cargo-deny licence enforcement.

#![no_std]

/// Returns a constant value used by the planted fixture root crate.
#[must_use]
pub const fn planted_value() -> u32 {
    1
}
