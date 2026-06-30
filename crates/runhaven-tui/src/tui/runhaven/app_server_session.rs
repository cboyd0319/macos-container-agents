//! RunHaven app-server session bridge for the Codex-vendored TUI spine.
//!
//! The upstream Codex TUI keeps typed app-server calls behind an
//! `AppServerSession`. RunHaven keeps the same boundary, but routes supported
//! calls to its local in-process facade and makes unsupported calls fail closed.

use std::path::PathBuf;
use std::time::Duration;
use std::time::Instant;

use runhaven_core::ui_contracts::ActiveRunListData;
use runhaven_core::ui_contracts::ActiveRunLogSnapshotData;
use runhaven_core::ui_contracts::AgentCatalogData;
use runhaven_core::ui_contracts::RunControlResultData;
use runhaven_core::ui_contracts::RunHavenDiagnosticsData;

use super::app_server_client::AppServerClient;
use super::app_server_client::AppServerRequestHandle;
use super::app_server_client::TypedRequestError;
use super::protocol::AppServerEvent;
use super::protocol::ClientRequest;
use super::protocol::RequestId;
use super::protocol::UnsupportedMethod;
use super::protocol::ValidateWorkspaceResponse;
use super::service::RunHavenTuiService;

#[derive(Debug, Clone, Eq, PartialEq)]
pub(crate) struct AppServerBootstrap {
    pub(crate) duration: Duration,
    pub(crate) workspace: PathBuf,
    pub(crate) agents: AgentCatalogData,
}

pub(crate) struct AppServerSession {
    client: AppServerClient,
    next_request_id: RequestId,
}

impl AppServerSession {
    pub(crate) fn start_in_process(service: RunHavenTuiService) -> Self {
        Self {
            client: AppServerClient::start_in_process(service),
            next_request_id: 1,
        }
    }

    pub(crate) async fn bootstrap(
        &mut self,
        workspace: PathBuf,
    ) -> Result<AppServerBootstrap, TypedRequestError> {
        let started_at = Instant::now();
        let validated = self.validate_workspace(workspace).await?;
        let workspace = PathBuf::from(validated.workspace);
        let agents = self.agent_catalog().await?;

        Ok(AppServerBootstrap {
            duration: started_at.elapsed(),
            workspace,
            agents,
        })
    }

    pub(crate) async fn agent_catalog(&mut self) -> Result<AgentCatalogData, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenAgentList { request_id })
            .await
    }

    pub(crate) async fn active_runs(&mut self) -> Result<ActiveRunListData, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenActiveRuns { request_id })
            .await
    }

    pub(crate) async fn diagnostics(
        &mut self,
        limit: usize,
    ) -> Result<RunHavenDiagnosticsData, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenDiagnostics { request_id, limit })
            .await
    }

    pub(crate) async fn validate_workspace(
        &mut self,
        workspace: PathBuf,
    ) -> Result<ValidateWorkspaceResponse, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenValidateWorkspace {
                request_id,
                workspace,
            })
            .await
    }

    pub(crate) async fn run_log_snapshot(
        &mut self,
        run_id: String,
        lines: u32,
        confirm_sensitive_output: bool,
    ) -> Result<ActiveRunLogSnapshotData, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenRunLogSnapshot {
                request_id,
                run_id,
                lines,
                confirm_sensitive_output,
            })
            .await
    }

    pub(crate) async fn stop_run(
        &mut self,
        run_id: String,
        confirm_stop: bool,
    ) -> Result<RunControlResultData, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenRunStop {
                request_id,
                run_id,
                confirm_stop,
            })
            .await
    }

    pub(crate) async fn kill_run(
        &mut self,
        run_id: String,
        confirm_kill: bool,
    ) -> Result<RunControlResultData, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenRunKill {
                request_id,
                run_id,
                confirm_kill,
            })
            .await
    }

    pub(crate) async fn repair_run(
        &mut self,
        run_id: String,
        confirm_repair: bool,
    ) -> Result<RunControlResultData, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::RunHavenRunRepair {
                request_id,
                run_id,
                confirm_repair,
            })
            .await
    }

    pub(crate) async fn unsupported(
        &mut self,
        method: UnsupportedMethod,
    ) -> Result<serde_json::Value, TypedRequestError> {
        let request_id = self.alloc_request_id();
        self.client
            .request_typed(ClientRequest::Unsupported { request_id, method })
            .await
    }

    pub(crate) async fn next_event(&mut self) -> Option<AppServerEvent> {
        self.client.next_event().await
    }

    pub(crate) fn request_handle(&self) -> AppServerRequestHandle {
        self.client.request_handle()
    }

    pub(crate) async fn shutdown(self) -> std::io::Result<()> {
        self.client.shutdown().await
    }

    fn alloc_request_id(&mut self) -> RequestId {
        let request_id = self.next_request_id;
        self.next_request_id = self.next_request_id.saturating_add(1);
        request_id
    }
}

#[cfg(test)]
#[path = "app_server_session_tests.rs"]
mod tests;
