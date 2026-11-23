// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Guards the `kernel-std` facade: every top-level public `kernel` item must be re-exported,
//! so a consumer can depend on `kernel-std` alone.

/// Source of the `kernel` crate root, where every public item is declared.
const KERNEL_SRC: &str = include_str!("../../kernel/src/lib.rs");

/// Source of the `kernel-std` crate root, which holds the `pub use kernel::{...}` list.
const FACADE_SRC: &str = include_str!("../src/lib.rs");

/// Item keywords whose top-level `pub` declarations the facade must re-export.
const ITEM_KEYWORDS: [&str; 6] = ["struct ", "enum ", "type ", "trait ", "static ", "const "];

/// Names of the top-level `pub` items declared in `source`, in declaration order.
fn public_items(source: &str) -> Vec<&str> {
    source
        .lines()
        .filter_map(|line| {
            let rest = line.strip_prefix("pub ")?;
            let rest = ITEM_KEYWORDS.iter().find_map(|kw| rest.strip_prefix(kw))?;
            let end = rest
                .find(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
                .unwrap_or(rest.len());
            Some(&rest[..end])
        })
        .filter(|name| !name.is_empty() && *name != "fn")
        .collect()
}

/// Names listed in the first `pub use kernel::{...}` block of `source`.
fn reexported_names(source: &str) -> Vec<&str> {
    let open = "pub use kernel::{";
    let Some(start) = source.find(open).map(|at| at + open.len()) else {
        return Vec::new();
    };
    let Some(len) = source[start..].find("};") else {
        return Vec::new();
    };
    source[start..start + len]
        .split(',')
        .map(str::trim)
        .filter(|name| !name.is_empty())
        .collect()
}

/// Every top-level public kernel item appears in the facade re-export list.
#[test]
fn facade_reexports_every_public_kernel_item() {
    let reexported = reexported_names(FACADE_SRC);
    let missing: Vec<&str> = public_items(KERNEL_SRC)
        .into_iter()
        .filter(|name| !reexported.contains(name))
        .collect();
    assert!(
        missing.is_empty(),
        "kernel-std does not re-export: {missing:?}"
    );
}

/// The scanner finds the kernel items this guard exists for, so an empty scan cannot pass silently.
#[test]
fn scanner_finds_known_kernel_items() {
    let items = public_items(KERNEL_SRC);
    for known in [
        "Kernel",
        "RevisionIdentity",
        "AssetRevision",
        "DEFAULT_POINTS",
    ] {
        assert!(items.contains(&known), "scanner missed {known}");
    }
    assert!(reexported_names(FACADE_SRC).contains(&"Kernel"));
}

/// A public item missing from the re-export list is reported by name.
#[test]
fn missing_reexport_is_detected() {
    let kernel = "pub struct Kept(u8);\npub enum Dropped {}\n    pub fn method() {}\n";
    let facade = "pub use kernel::{\n    Kept,\n};\n";
    let reexported = reexported_names(facade);
    let missing: Vec<&str> = public_items(kernel)
        .into_iter()
        .filter(|name| !reexported.contains(name))
        .collect();
    assert_eq!(missing, ["Dropped"]);
}

/// Boundary shapes: a facade with no re-export block yields no names, and `pub const fn` is no item.
#[test]
fn scanner_boundaries() {
    assert_eq!(reexported_names("use std::fmt;\n"), Vec::<&str>::new());
    assert_eq!(
        reexported_names("pub use kernel::{ Unclosed"),
        Vec::<&str>::new()
    );
    assert_eq!(
        public_items("pub const fn helper() {}\npub const MAX: u8 = 1;\n"),
        ["MAX"]
    );
}
