use super::*;
use crate::tui::runhaven::protocol::UnsupportedMethod;
use crate::tui::runhaven::protocol::ValidateWorkspaceResponse;
use crate::tui::runhaven::service::confirm_required_preview_for_tests;
use runhaven_core::ui_contracts::AgentCatalogData;
use serde::Deserialize;

fn test_client(capacity: usize) -> RunHavenInProcessClient {
    RunHavenInProcessClient::start(RunHavenTuiService::new(), capacity)
}

#[tokio::test]
async fn request_typed_returns_agent_catalog() {
    let client = test_client(4);

    let catalog: AgentCatalogData = client
        .request_typed(ClientRequest::RunHavenAgentList { request_id: 1 })
        .await
        .expect("agent catalog");

    assert!(
        catalog.agents.iter().any(|agent| agent.name == "codex"),
        "expected codex profile in catalog"
    );

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn request_handle_can_cancel_pending_request() {
    let client = test_client(4);
    let handle = client.request_handle();
    let pending = handle
        .begin_request_typed::<AgentCatalogData>(ClientRequest::RunHavenAgentList { request_id: 7 })
        .await
        .expect("pending request");

    let cancelled = pending.cancel();
    assert_eq!(
        cancelled,
        CancelledRequest {
            request_id: 7,
            method: "runhaven/agent/list".to_string(),
        }
    );

    let catalog: AgentCatalogData = handle
        .request_typed(ClientRequest::RunHavenAgentList { request_id: 8 })
        .await
        .expect("worker remains usable after cancellation");
    assert!(!catalog.agents.is_empty());

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn next_event_reads_server_notifications_and_requests() {
    let mut client = test_client(4);
    let handle = client.request_handle();

    handle
        .emit_notification(ServerNotification::TranscriptDelta {
            text: "hello".to_string(),
        })
        .await
        .expect("emit transcript");
    handle
        .emit_server_request(ServerRequest::Confirm {
            request_id: 9,
            prompt: "Launch?".to_string(),
        })
        .await
        .expect("emit request");

    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerNotification(
            ServerNotification::TranscriptDelta {
                text: "hello".to_string()
            }
        ))
    );
    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerRequest(ServerRequest::Confirm {
            request_id: 9,
            prompt: "Launch?".to_string(),
        }))
    );

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn shutdown_closes_backend_without_pending_events() {
    let client = test_client(1);
    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn wrapper_client_supports_request_events_and_server_request_resolution() {
    let mut client = AppServerClient::start_in_process(RunHavenTuiService::new());
    let handle = client.request_handle();

    let catalog: AgentCatalogData = client
        .request_typed(ClientRequest::RunHavenAgentList { request_id: 20 })
        .await
        .expect("agent catalog");
    assert!(!catalog.agents.is_empty());

    handle
        .emit_server_request(ServerRequest::Confirm {
            request_id: 21,
            prompt: "Launch?".to_string(),
        })
        .await
        .expect("emit server request");
    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerRequest(ServerRequest::Confirm {
            request_id: 21,
            prompt: "Launch?".to_string(),
        }))
    );

    client
        .resolve_server_request(21, Value::Bool(true))
        .await
        .expect("resolve server request");
    let duplicate = client
        .reject_server_request(21, "already resolved".to_string())
        .await
        .expect_err("resolved request should not reject again");
    assert_eq!(duplicate.kind(), io::ErrorKind::NotFound);

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn lossless_notifications_are_delivered_in_order() {
    let mut client = test_client(8);
    let handle = client.request_handle();
    let launch = confirm_required_preview_for_tests()
        .plan
        .expect("test launch");
    let plan = launch.data;

    for notification in [
        ServerNotification::TranscriptDelta {
            text: "streamed text".to_string(),
        },
        ServerNotification::TurnCompleted {
            turn_id: "turn-1".to_string(),
        },
        ServerNotification::LaunchPrepared {
            plan_id: "plan-1".to_string(),
            plan: Box::new(plan.clone()),
        },
    ] {
        handle
            .emit_notification(notification)
            .await
            .expect("emit notification");
    }

    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerNotification(
            ServerNotification::TranscriptDelta {
                text: "streamed text".to_string()
            }
        ))
    );
    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerNotification(
            ServerNotification::TurnCompleted {
                turn_id: "turn-1".to_string()
            }
        ))
    );
    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerNotification(
            ServerNotification::LaunchPrepared {
                plan_id: "plan-1".to_string(),
                plan: Box::new(plan)
            }
        ))
    );

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn best_effort_noise_drops_and_flushes_lag_before_lossless_event() {
    let mut client = test_client(1);
    let handle = client.request_handle();

    handle
        .emit_notification(ServerNotification::Progress {
            message: "queued".to_string(),
        })
        .await
        .expect("queue first progress");
    handle
        .emit_notification(ServerNotification::Progress {
            message: "dropped one".to_string(),
        })
        .await
        .expect("drop second progress");
    handle
        .emit_notification(ServerNotification::LogDelta {
            text: "dropped two".to_string(),
        })
        .await
        .expect("drop log noise");

    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerNotification(
            ServerNotification::Progress {
                message: "queued".to_string()
            }
        ))
    );

    let send_handle = handle.clone();
    let send_lossless = tokio::spawn(async move {
        send_handle
            .emit_notification(ServerNotification::TurnCompleted {
                turn_id: "turn-2".to_string(),
            })
            .await
    });

    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::Lagged { skipped: 2 })
    );
    assert_eq!(
        client.next_event().await,
        Some(AppServerEvent::ServerNotification(
            ServerNotification::TurnCompleted {
                turn_id: "turn-2".to_string()
            }
        ))
    );
    send_lossless
        .await
        .expect("join lossless sender")
        .expect("lossless sender");

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn unsupported_method_matrix_fails_closed() {
    let client = test_client(4);

    for method in UnsupportedMethod::ALL {
        let error = client
            .request_typed::<Value>(ClientRequest::Unsupported {
                request_id: 11,
                method: *method,
            })
            .await
            .expect_err("unsupported method should fail");

        match error {
            TypedRequestError::Unsupported {
                method: actual,
                family,
            } => {
                assert_eq!(actual, method.method());
                assert_eq!(family, method.family());
            }
            other => panic!("expected unsupported error for {method:?}, got {other:?}"),
        }
    }

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn request_typed_surfaces_validation_errors() {
    let root = tempfile::tempdir().expect("root");
    let missing = root.path().join("missing");
    let client = test_client(4);

    let error = client
        .request_typed::<ValidateWorkspaceResponse>(ClientRequest::RunHavenValidateWorkspace {
            request_id: 12,
            workspace: missing,
        })
        .await
        .expect_err("missing workspace should fail validation");

    assert!(matches!(error, TypedRequestError::Validation { .. }));

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn request_typed_surfaces_backend_failures() {
    let client = test_client(4);

    let error = client
        .request_typed::<Value>(ClientRequest::BackendFailureForTest {
            request_id: 13,
            message: "backend unavailable".to_string(),
        })
        .await
        .expect_err("test backend failure should fail");

    assert!(matches!(
        error,
        TypedRequestError::Backend { message, .. } if message == "backend unavailable"
    ));

    client.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn request_typed_surfaces_deserialize_errors() {
    #[derive(Debug, Deserialize)]
    #[allow(dead_code)]
    struct WrongResponse {
        missing_field: String,
    }

    let client = test_client(4);

    let error = client
        .request_typed::<WrongResponse>(ClientRequest::RunHavenAgentList { request_id: 14 })
        .await
        .expect_err("wrong response type should fail decode");

    match error {
        TypedRequestError::Deserialize { method, source } => {
            assert_eq!(method, "runhaven/agent/list");
            assert!(source.to_string().contains("missing_field"));
        }
        other => panic!("expected deserialize error, got {other:?}"),
    }

    client.shutdown().await.expect("shutdown");
}
