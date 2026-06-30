//! Narrow vendored `codex-models-manager` surface for TUI tests.
//!
//! RunHaven keeps this crate under the original Codex package and library name,
//! but only exposes the bundled model catalog parser needed by vendored TUI
//! test helpers. The upstream manager's remote cache, login, and telemetry
//! behavior remain dormant.

pub fn bundled_models_response()
-> std::result::Result<codex_protocol::openai_models::ModelsResponse, serde_json::Error> {
    serde_json::from_str(include_str!("../models.json"))
}
