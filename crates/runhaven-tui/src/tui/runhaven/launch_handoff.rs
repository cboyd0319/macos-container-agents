//! Foreground RunHaven launch through the Codex terminal handoff boundary.
//!
//! Widgets and backend facade tasks prepare launch intent only. This module is
//! the single TUI owner that may call `launch_run_plan`, and only after Codex
//! has released terminal modes and stdin ownership.

use std::future::Future;
use std::pin::Pin;

use anyhow::Context;
use anyhow::Result;
use runhaven_core::runtime::launch::launch_run_plan;
use runhaven_core::runtime::plans::AgentRunPlan;

use super::service::PreparedLaunch;
use crate::tui::codex_runtime;
use crate::tui::terminal_title::clear_terminal_title;

pub(crate) async fn launch_prepared(
    tui: &mut codex_runtime::Tui,
    launch: PreparedLaunch,
) -> Result<i32> {
    launch_prepared_with_ops(tui, launch, |plan| async move { launch_run_plan(&plan) }).await
}

trait HandoffOps {
    fn clear_title(&mut self);
    fn clear_images(&mut self) -> Result<()>;
    fn clear_terminal(&mut self) -> Result<()>;
    fn with_restored<'a, R, F, Fut>(&'a mut self, f: F) -> Pin<Box<dyn Future<Output = R> + 'a>>
    where
        F: FnOnce() -> Fut + 'a,
        Fut: Future<Output = R> + 'a,
        R: 'a;
}

impl HandoffOps for codex_runtime::Tui {
    fn clear_title(&mut self) {
        let _ = clear_terminal_title();
    }

    fn clear_images(&mut self) -> Result<()> {
        self.clear_pet_images()
            .context("clear terminal images before launch handoff")
    }

    fn clear_terminal(&mut self) -> Result<()> {
        self.terminal
            .clear()
            .context("clear terminal before launch handoff")
    }

    fn with_restored<'a, R, F, Fut>(&'a mut self, f: F) -> Pin<Box<dyn Future<Output = R> + 'a>>
    where
        F: FnOnce() -> Fut + 'a,
        Fut: Future<Output = R> + 'a,
        R: 'a,
    {
        Box::pin(codex_runtime::Tui::with_restored(
            self,
            codex_runtime::RestoreMode::Full,
            f,
        ))
    }
}

async fn launch_prepared_with_ops<O, F, Fut>(
    ops: &mut O,
    launch: PreparedLaunch,
    launcher: F,
) -> Result<i32>
where
    O: HandoffOps,
    F: FnOnce(AgentRunPlan) -> Fut,
    Fut: Future<Output = Result<i32>>,
{
    let plan = launch.executable;
    ops.clear_title();
    ops.clear_images()?;
    ops.clear_terminal()?;

    ops.with_restored(move || launcher(plan)).await
}

#[cfg(test)]
#[path = "launch_handoff_tests.rs"]
mod tests;
