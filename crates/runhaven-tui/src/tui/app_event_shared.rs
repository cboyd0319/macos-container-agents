//! Shared type bridge for activating the vendored Codex `app_event.rs`.
//!
//! These are narrow inert leaf types whose owning upstream modules are still
//! dormant because they carry broader app, chat, filesystem, or history
//! behavior. Remove this bridge as the real modules are promoted.

pub(crate) mod app {
    pub(crate) mod app_server_requests {
        use codex_app_server_protocol::RequestId as AppServerRequestId;

        #[derive(Debug, Clone, PartialEq, Eq)]
        pub(crate) enum ResolvedAppServerRequest {
            ExecApproval {
                id: String,
            },
            FileChangeApproval {
                id: String,
            },
            PermissionsApproval {
                id: String,
            },
            UserInput {
                call_id: String,
            },
            McpElicitation {
                server_name: String,
                request_id: AppServerRequestId,
            },
        }
    }
}

pub(crate) mod app_server_session {
    use codex_app_server_protocol::Turn;

    #[derive(Debug)]
    pub(crate) struct ThreadSessionState;

    #[derive(Debug)]
    pub(crate) struct AppServerStartedThread {
        pub(crate) session: ThreadSessionState,
        pub(crate) turns: Vec<Turn>,
    }
}

pub(crate) mod chatwidget {
    use codex_protocol::user_input::TextElement;

    #[derive(Debug, Clone, PartialEq)]
    pub(crate) struct UserMessage {
        pub(crate) text: String,
        pub(crate) local_images: Vec<()>,
        pub(crate) remote_image_urls: Vec<String>,
        pub(crate) text_elements: Vec<TextElement>,
        pub(crate) mention_bindings: Vec<()>,
    }

    #[derive(Debug, Clone, Default, PartialEq, Eq)]
    pub(crate) struct StatusLineGitSummary;
}

pub(crate) mod goal_files {
    use codex_protocol::user_input::TextElement;

    #[derive(Clone, Debug, Default)]
    pub(crate) struct GoalDraft {
        pub(crate) objective: String,
        pub(crate) text_elements: Vec<TextElement>,
        pub(crate) pending_pastes: Vec<(String, String)>,
        pub(crate) local_images: Vec<()>,
        pub(crate) remote_image_urls: Vec<String>,
    }
}

pub(crate) mod history_cell {
    use std::collections::HashMap;

    use codex_app_server_protocol::ToolRequestUserInputAnswer;
    use codex_app_server_protocol::ToolRequestUserInputQuestion;
    use codex_protocol::approvals::ExecPolicyAmendment;
    use codex_protocol::approvals::NetworkPolicyAmendment;
    use ratatui::style::Stylize;
    use ratatui::text::Line;
    use ratatui::text::Span;

    pub(crate) trait HistoryCell: std::fmt::Debug + Send + Sync {
        fn display_lines(&self, width: u16) -> Vec<Line<'static>>;

        fn raw_lines(&self) -> Vec<Line<'static>> {
            plain_lines(self.display_lines(u16::MAX))
        }
    }

    pub(crate) fn plain_lines(
        lines: impl IntoIterator<Item = Line<'static>>,
    ) -> Vec<Line<'static>> {
        lines
            .into_iter()
            .map(|line| {
                let text = line
                    .spans
                    .into_iter()
                    .map(|span| span.content.into_owned())
                    .collect::<String>();
                Line::from(text)
            })
            .collect()
    }

    #[derive(Debug)]
    pub(crate) struct PlainHistoryCell {
        lines: Vec<Line<'static>>,
    }

    impl PlainHistoryCell {
        pub(crate) fn new(lines: Vec<Line<'static>>) -> Self {
            Self { lines }
        }
    }

    impl HistoryCell for PlainHistoryCell {
        fn display_lines(&self, _width: u16) -> Vec<Line<'static>> {
            self.lines.clone()
        }
    }

    #[derive(Debug)]
    pub(crate) struct WebHyperlinkHistoryCell {
        lines: Vec<Line<'static>>,
    }

    impl WebHyperlinkHistoryCell {
        pub(crate) fn new(lines: Vec<Line<'static>>) -> Self {
            Self { lines }
        }
    }

    impl HistoryCell for WebHyperlinkHistoryCell {
        fn display_lines(&self, _width: u16) -> Vec<Line<'static>> {
            self.lines.clone()
        }
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub(crate) enum ReviewDecision {
        Approved,
        ApprovedExecpolicyAmendment {
            proposed_execpolicy_amendment: ExecPolicyAmendment,
        },
        ApprovedForSession,
        NetworkPolicyAmendment {
            network_policy_amendment: NetworkPolicyAmendment,
        },
        Denied,
        TimedOut,
        Abort,
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub(crate) enum ApprovalDecisionSubject {
        Command(Vec<String>),
        NetworkAccess { target: String },
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub(crate) enum ApprovalDecisionActor {
        User,
        Guardian,
    }

    impl ApprovalDecisionActor {
        fn label(self) -> &'static str {
            match self {
                ApprovalDecisionActor::User => "You",
                ApprovalDecisionActor::Guardian => "Guardian",
            }
        }
    }

    pub(crate) fn new_approval_decision_cell(
        subject: ApprovalDecisionSubject,
        decision: ReviewDecision,
        actor: ApprovalDecisionActor,
    ) -> Box<dyn HistoryCell> {
        let subject_text = match subject {
            ApprovalDecisionSubject::Command(command) => {
                let command = crate::exec_command::strip_bash_lc_and_escape(&command);
                if command.is_empty() {
                    "this command".to_string()
                } else {
                    format!("`{command}`")
                }
            }
            ApprovalDecisionSubject::NetworkAccess { target } => {
                format!("network access to {target}")
            }
        };
        let action = match decision {
            ReviewDecision::Approved => "approved",
            ReviewDecision::ApprovedExecpolicyAmendment { .. } => "approved and saved as a rule",
            ReviewDecision::ApprovedForSession => "approved for this session",
            ReviewDecision::NetworkPolicyAmendment { .. } => "saved as a network rule",
            ReviewDecision::Denied => "denied",
            ReviewDecision::TimedOut => "timed out",
            ReviewDecision::Abort => "cancelled",
        };
        Box::new(PlainHistoryCell::new(vec![Line::from(vec![
            Span::from("- ").dim(),
            Span::from(actor.label()).bold(),
            Span::from(format!(" {action} {subject_text}")),
        ])]))
    }

    pub(crate) fn new_info_event(message: String, hint: Option<String>) -> PlainHistoryCell {
        let mut spans = vec![Span::from("- ").dim(), Span::from(message)];
        if let Some(hint) = hint {
            spans.push(Span::from(" "));
            spans.push(Span::from(hint).dark_gray());
        }
        PlainHistoryCell::new(vec![Line::from(spans)])
    }

    pub(crate) fn new_error_event(message: String) -> PlainHistoryCell {
        PlainHistoryCell::new(vec![Line::from(vec![
            Span::from("Error: ").red(),
            Span::from(message).red(),
        ])])
    }

    #[derive(Debug)]
    pub(crate) struct RequestUserInputResultCell {
        pub(crate) questions: Vec<ToolRequestUserInputQuestion>,
        pub(crate) answers: HashMap<String, ToolRequestUserInputAnswer>,
        pub(crate) interrupted: bool,
    }

    impl HistoryCell for RequestUserInputResultCell {
        fn display_lines(&self, _width: u16) -> Vec<Line<'static>> {
            let total = self.questions.len();
            let answered = self
                .questions
                .iter()
                .filter(|question| {
                    self.answers
                        .get(&question.id)
                        .is_some_and(|answer| !answer.answers.is_empty())
                })
                .count();
            let suffix = if self.interrupted {
                " (interrupted)"
            } else {
                ""
            };
            let mut lines = vec![Line::from(format!(
                "- Questions {answered}/{total} answered{suffix}"
            ))];
            for question in &self.questions {
                let answer = self.answers.get(&question.id);
                let status = if answer.is_some_and(|answer| !answer.answers.is_empty()) {
                    "answered"
                } else {
                    "unanswered"
                };
                lines.push(Line::from(format!("  - {} ({status})", question.question)));
            }
            lines
        }
    }
}

pub(crate) mod hooks_rpc {
    use codex_app_server_protocol::HookMetadata;
    use codex_app_server_protocol::HookTrustStatus;

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub(crate) struct HookTrustUpdate {
        pub(crate) key: String,
        pub(crate) current_hash: String,
    }

    pub(crate) fn hook_needs_review(hook: &HookMetadata) -> bool {
        matches!(
            hook.trust_status,
            HookTrustStatus::Untrusted | HookTrustStatus::Modified
        )
    }
}

pub(crate) mod workspace_messages {
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub(crate) struct WorkspaceHeadlineFetchResult;
}

pub(crate) mod session_log {
    use crate::app_command::AppCommand;
    use crate::app_event::AppEvent;

    pub(crate) fn log_inbound_app_event(_event: &AppEvent) {}

    pub(crate) fn log_outbound_op(_op: &AppCommand) {}

    pub(crate) fn log_session_end() {}
}
