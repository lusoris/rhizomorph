<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# Known defects of the design reference code

The design input by the operator came with reference code. Eight defects
were found in it. **The reference code is not copied into this repository.**
Each defect is fixed in the planned implementation, in the phase named
below ([`phases.md`](phases.md)). HISS ids refer to [`AGENTS.md`](../../AGENTS.md);
"none" means no invariant there names the defect.

| # | Defect | Why it matters | HISS | Planned fix | Phase |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Declares `no_std` yet imports `std::sync`, `std::time` and tokio | The kernel is not portable or testable without an async runtime, and the declaration is false | none | A `no_std` core crate and a separate `std` adapter ([ADR-0001](../adr/0001-tier-model.md)) | P1 |
| 2 | Calls `.expect()` on lock results | A poisoned lock turns into a panic inside the kernel | HISS-07 | Handle every lock result and wrap errors with context; no `.unwrap()` or `.expect()` outside tests | P1 |
| 3 | `touched_by_leases` is a 64-bit mask indexed by `lease % 64`; leases 64 and above collide, and revoke still scans every point, so the claim of constant-time revoke is false | A colliding lease can leave stale slots in force or clear too much; the stated bound is wrong | HISS-02 (every loop has a stated bound) | A per-lease point index, so revoke visits only the points that lease holds, each with at most 16 slots ([ADR-0002](../adr/0002-priority-array-and-leases.md)) | P1 |
| 4 | Takes a write lock on `RwLock<Vec<_>>` for every telemetry ingress, and calls `Instant::now()` on the hot path | Every writer serializes behind one lock, and a clock read is added to each update | none | Finer locking and a time value passed into the core; the choice is measured in P1 | P1 |
| 5 | The priority enum covers 7 of 16 levels (8 in the specification text, with Minimum On/Off) | Valid levels cannot be written; the type does not match the standard | none | A `u8` newtype validated to 1..=16 with named constants for the assigned levels ([ADR-0002](../adr/0002-priority-array-and-leases.md)) | P1 |
| 6 | Relinquishing the last slot leaves the present value empty and emits no COV event | A watcher never learns that the override ended | HISS-15 (negative and boundary tests of every public interface) | Define the relinquish default, set the present value to it and emit the event | P1 |
| 7 | Deadband 0.0 on floats and the `PartialEq` of `Value` (NaN, Int against Float) are undefined | Equal-looking updates may fire or be dropped by accident | HISS-15 | Define both in tests first ([ADR-0002](../adr/0002-priority-array-and-leases.md)) | P1 |
| 8 | The WIT priority enum omits manual life safety | None: this is on purpose | none | Keep it. Guests never take level 1; stated in [ADR-0003](../adr/0003-wit-contract-push-model.md) | P3 |
