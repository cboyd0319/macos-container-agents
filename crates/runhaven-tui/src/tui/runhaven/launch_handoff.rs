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
mod tests {
    use std::cell::RefCell;
    use std::rc::Rc;

    use anyhow::Result;

    use super::*;
    use crate::tui::runhaven::service::confirm_required_preview_for_tests;

    #[derive(Clone, Default)]
    struct RecordingOps {
        events: Rc<RefCell<Vec<&'static str>>>,
    }

    impl HandoffOps for RecordingOps {
        fn clear_title(&mut self) {
            self.events.borrow_mut().push("clear_title");
        }

        fn clear_images(&mut self) -> Result<()> {
            self.events.borrow_mut().push("clear_images");
            Ok(())
        }

        fn clear_terminal(&mut self) -> Result<()> {
            self.events.borrow_mut().push("clear_terminal");
            Ok(())
        }

        fn with_restored<'a, R, F, Fut>(&'a mut self, f: F) -> Pin<Box<dyn Future<Output = R> + 'a>>
        where
            F: FnOnce() -> Fut + 'a,
            Fut: Future<Output = R> + 'a,
            R: 'a,
        {
            self.events.borrow_mut().push("with_restored");
            Box::pin(async move { f().await })
        }
    }

    #[tokio::test]
    async fn prepared_launch_handoff_restores_terminal_before_launcher() {
        let launch = confirm_required_preview_for_tests()
            .plan
            .expect("prepared launch");
        let mut ops = RecordingOps::default();
        let events = Rc::clone(&ops.events);

        let exit_code = launch_prepared_with_ops(&mut ops, launch, move |_plan| {
            let events = Rc::clone(&events);
            async move {
                events.borrow_mut().push("launch");
                Ok(7)
            }
        })
        .await
        .expect("launcher result");

        assert_eq!(exit_code, 7);
        assert_eq!(
            ops.events.borrow().as_slice(),
            [
                "clear_title",
                "clear_images",
                "clear_terminal",
                "with_restored",
                "launch"
            ]
        );
    }

    #[tokio::test]
    async fn prepared_launch_handoff_uses_executable_plan_not_display_command() {
        let mut launch = confirm_required_preview_for_tests()
            .plan
            .expect("prepared launch");
        launch.data.command = "container run --tampered display string".to_string();
        let mut ops = RecordingOps::default();

        let exit_code = launch_prepared_with_ops(&mut ops, launch, |plan| async move {
            assert_eq!(
                plan.command,
                [
                    "container",
                    "run",
                    "--name",
                    "runhaven-codex",
                    "runhaven/codex:0.1.0"
                ]
            );
            Ok(7)
        })
        .await
        .expect("launcher result");

        assert_eq!(exit_code, 7);
    }
}
