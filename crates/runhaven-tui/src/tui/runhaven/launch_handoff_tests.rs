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
