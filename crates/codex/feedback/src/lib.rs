//! Narrow vendored `codex-feedback` surface for TUI feedback display models.
//!
//! RunHaven keeps this crate under the original Codex package and library name,
//! but does not expose the upstream upload, logging, Sentry, or login-tagging
//! behavior until that boundary has a RunHaven security design.

pub mod feedback_diagnostics;

pub use feedback_diagnostics::FEEDBACK_DIAGNOSTICS_ATTACHMENT_FILENAME;
pub use feedback_diagnostics::FeedbackDiagnostic;
pub use feedback_diagnostics::FeedbackDiagnostics;

/// Filename used for the redacted `codex doctor --json` feedback attachment.
pub const DOCTOR_REPORT_ATTACHMENT_FILENAME: &str = "codex-doctor-report.json";
/// Filename used for the Windows sandbox log feedback attachment.
pub const WINDOWS_SANDBOX_LOG_ATTACHMENT_FILENAME: &str = "windows-sandbox.log";
