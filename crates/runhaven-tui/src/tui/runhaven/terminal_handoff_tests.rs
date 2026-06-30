use std::ffi::OsString;

use super::*;

#[test]
fn smoke_mode_parser_accepts_named_modes_only() {
    assert_eq!(
        HandoffSmokeMode::parse(&OsString::from("success")),
        Some(HandoffSmokeMode::Success)
    );
    assert_eq!(
        HandoffSmokeMode::parse(&OsString::from(" ERROR ")),
        Some(HandoffSmokeMode::EarlyError)
    );
    assert_eq!(HandoffSmokeMode::parse(&OsString::from("agent")), None);
}

#[test]
fn success_smoke_uses_exact_harmless_command() {
    let (program, args) = HandoffSmokeMode::Success.command();
    assert_eq!(program, "/usr/bin/printf");
    assert_eq!(args, &["%s\n", SUCCESS_MARKER]);
}

#[test]
fn early_error_smoke_uses_missing_absolute_command() {
    let (program, args) = HandoffSmokeMode::EarlyError.command();
    assert_eq!(program, "/__runhaven_missing_terminal_handoff_child__");
    assert!(args.is_empty());
    let err = run_child(HandoffSmokeMode::EarlyError).expect_err("missing child");
    assert_eq!(err.kind(), std::io::ErrorKind::NotFound);
}
