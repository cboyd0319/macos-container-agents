//! Vendored terminal-graphics and pet modules from openai/codex.
//!
//! These modules are copied from openai/codex (`codex-rs/tui` pets and
//! `codex-rs/terminal-detection`), licensed under Apache-2.0, copyright 2025
//! OpenAI. They were modified by RunHaven on 2026-06-26: import paths were
//! adapted to this module layout, and the upstream `tracing` logging and TUI /
//! asset-pack couplings were removed. The vendored code is a faithful copy, not
//! a rewrite.
//!
//! The full license text is in `licenses/codex-Apache-2.0.txt` and the required
//! attribution notice is in `THIRD_PARTY_NOTICES.md` at the repo root.
//!
//! Nothing here is wired into the RunHaven TUI yet; the modules exist so the
//! hero/pet integration can build on them in a later slice. The per-module
//! `#[allow(...)]` attributes keep the currently-unused vendored code compiling
//! cleanly under `cargo clippy --all-targets -- -D warnings`.

use std::path::Path;
use std::path::PathBuf;

#[allow(dead_code, clippy::all, clippy::pedantic)]
pub(crate) mod terminal_detection;

#[allow(dead_code, clippy::all, clippy::pedantic)]
pub(crate) mod sixel;

#[allow(dead_code, clippy::all, clippy::pedantic)]
pub(crate) mod image_protocol;

#[allow(dead_code, clippy::all, clippy::pedantic)]
pub(crate) mod catalog;

#[allow(dead_code, clippy::all, clippy::pedantic)]
pub(crate) mod model;

#[allow(dead_code, clippy::all, clippy::pedantic)]
pub(crate) mod frames;

#[allow(dead_code, clippy::all, clippy::pedantic)]
pub(crate) mod animation;

/// Resolve a built-in pet spritesheet path under a Codex/RunHaven home.
///
/// Codex defines this in `tui/src/pets/mod.rs` (which RunHaven does not vendor)
/// as `pub(crate) fn builtin_spritesheet_path(codex_home: &Path, file: &str) ->
/// PathBuf`. `model.rs` calls it through `super::builtin_spritesheet_path`, so
/// the signature is kept exact. The body is a placeholder until RunHaven wires
/// in real asset storage; it is not used by any active code path yet.
#[allow(dead_code)]
pub(crate) fn builtin_spritesheet_path(codex_home: &Path, file: &str) -> PathBuf {
    codex_home.join("pets").join("assets").join(file)
}
