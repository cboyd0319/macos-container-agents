use super::*;
use crate::tui::runhaven::service::confirm_required_preview_for_tests;

#[test]
fn launch_prepared_notification_serializes_display_plan_only() {
    let launch = confirm_required_preview_for_tests()
        .plan
        .expect("prepared launch");
    let notification = ServerNotification::LaunchPrepared {
        plan_id: "codex-plan".to_string(),
        plan: Box::new(launch.data),
    };

    let value = serde_json::to_value(&notification).expect("notification json");
    let plan = value
        .get("params")
        .and_then(|params| params.get("plan"))
        .expect("plan payload");

    assert_eq!(
        value.get("method").and_then(|method| method.as_str()),
        Some("launchPrepared")
    );
    assert!(plan.get("command").expect("command").is_string());
    assert!(
        plan.get("preflightCommands")
            .and_then(|commands| commands.as_array())
            .expect("preflight commands")
            .iter()
            .all(serde_json::Value::is_string)
    );
    assert!(plan.get("executable").is_none());
    assert!(plan.get("runId").is_none());
    assert!(plan.get("command").is_some());

    let round_trip: ServerNotification =
        serde_json::from_value(value).expect("round-trip notification");
    assert_eq!(round_trip, notification);

    let protocol_source = include_str!("protocol.rs");
    let prepared_launch_marker = ["Prepared", "Launch"].concat();
    let executable_plan_marker = ["Agent", "Run", "Plan"].concat();
    let display_plan_field = ["plan", ": Box<", "LaunchPlanData", ">"].concat();
    assert!(protocol_source.contains(&display_plan_field));
    assert!(!protocol_source.contains(&prepared_launch_marker));
    assert!(!protocol_source.contains(&executable_plan_marker));
}

#[test]
fn run_log_snapshot_request_uses_runhaven_method() {
    let request = ClientRequest::RunHavenRunLogSnapshot {
        request_id: 42,
        run_id: "run-123".to_string(),
        lines: 100,
        confirm_sensitive_output: true,
    };

    assert_eq!(request.request_id(), 42);
    assert_eq!(request.method(), "runhaven/run/logSnapshot");
}
