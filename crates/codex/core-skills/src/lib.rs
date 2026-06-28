//! Narrow vendored `codex-core-skills` surface for TUI data models.
//!
//! RunHaven keeps this crate under the original Codex package and library name,
//! but only exposes the inert skill model surface needed by the vendored TUI.
//! The broader upstream crate loads host skills and integrates with Codex auth,
//! plugin, and model-provider surfaces that have not been promoted into
//! RunHaven's active security boundary.

#![allow(dead_code)]

pub mod model;

pub use model::HostSkillsSnapshot;
pub use model::SkillDependencies;
pub use model::SkillError;
pub use model::SkillInterface;
pub use model::SkillLoadOutcome;
pub use model::SkillMetadata;
pub use model::SkillPolicy;
pub use model::SkillToolDependency;
pub use model::filter_skill_load_outcome_for_product;
