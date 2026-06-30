use super::*;

#[tokio::test]
async fn bootstrap_routes_supported_calls_to_runhaven_service() {
    let workspace = std::env::current_dir().expect("current dir");
    let mut session = AppServerSession::start_in_process(RunHavenTuiService::new());

    let bootstrap = session
        .bootstrap(workspace.clone())
        .await
        .expect("bootstrap should succeed");

    assert_eq!(bootstrap.workspace, workspace);
    assert!(!bootstrap.agents.agents.is_empty());
    assert!(bootstrap.duration < Duration::from_secs(30));
    session.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn active_runs_and_diagnostics_route_to_runhaven_service() {
    let mut session = AppServerSession::start_in_process(RunHavenTuiService::new());

    let active_runs = session.active_runs().await.expect("active runs");
    let diagnostics = session.diagnostics(5).await.expect("diagnostics");

    assert!(active_runs.runs.iter().all(|run| !run.run_id.is_empty()));
    assert!(!diagnostics.auth_status.status.is_empty());
    session.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn unsupported_methods_fail_closed() {
    let mut session = AppServerSession::start_in_process(RunHavenTuiService::new());

    for unsupported_method in [
        UnsupportedMethod::FsReadFile,
        UnsupportedMethod::McpServerList,
        UnsupportedMethod::PluginList,
        UnsupportedMethod::AppList,
        UnsupportedMethod::HooksList,
        UnsupportedMethod::AccountLoginStart,
        UnsupportedMethod::EnvironmentAdd,
    ] {
        let error = session
            .unsupported(unsupported_method)
            .await
            .expect_err("unsupported request should fail");

        match error {
            TypedRequestError::Unsupported { method, family } => {
                assert_eq!(method, unsupported_method.method());
                assert_eq!(family, unsupported_method.family());
            }
            other => panic!("expected unsupported error, got {other:?}"),
        }
    }
    session.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn run_log_snapshot_rejects_invalid_line_count_before_backend_lookup() {
    let mut session = AppServerSession::start_in_process(RunHavenTuiService::new());

    let error = session
        .run_log_snapshot("not-a-real-run".to_string(), 0, true)
        .await
        .expect_err("invalid line count should fail validation");

    match error {
        TypedRequestError::Validation { method, message } => {
            assert_eq!(method, "runhaven/run/logSnapshot");
            assert!(message.contains("between 1 and 500"));
        }
        other => panic!("expected validation error, got {other:?}"),
    }

    session.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn run_log_snapshot_requires_sensitive_output_confirmation_before_backend_lookup() {
    let mut session = AppServerSession::start_in_process(RunHavenTuiService::new());

    let error = session
        .run_log_snapshot("not-a-real-run".to_string(), 100, false)
        .await
        .expect_err("missing confirmation should fail validation");

    match error {
        TypedRequestError::Validation { method, message } => {
            assert_eq!(method, "runhaven/run/logSnapshot");
            assert!(message.contains("Confirm raw log viewing"));
        }
        other => panic!("expected validation error, got {other:?}"),
    }

    session.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn run_control_requires_confirmation_before_backend_lookup() {
    let mut session = AppServerSession::start_in_process(RunHavenTuiService::new());

    let error = session
        .stop_run("not-a-real-run".to_string(), false)
        .await
        .expect_err("stop without confirmation should fail validation");
    match error {
        TypedRequestError::Validation { method, message } => {
            assert_eq!(method, "runhaven/run/stop");
            assert!(message.contains("Confirm stop"));
        }
        other => panic!("expected validation error, got {other:?}"),
    }

    let error = session
        .kill_run("not-a-real-run".to_string(), false)
        .await
        .expect_err("hard stop without confirmation should fail validation");
    match error {
        TypedRequestError::Validation { method, message } => {
            assert_eq!(method, "runhaven/run/kill");
            assert!(message.contains("Confirm hard stop"));
        }
        other => panic!("expected validation error, got {other:?}"),
    }

    let error = session
        .repair_run("not-a-real-run".to_string(), false)
        .await
        .expect_err("repair without confirmation should fail validation");
    match error {
        TypedRequestError::Validation { method, message } => {
            assert_eq!(method, "runhaven/run/repair");
            assert!(message.contains("Confirm repair"));
        }
        other => panic!("expected validation error, got {other:?}"),
    }

    session.shutdown().await.expect("shutdown");
}
