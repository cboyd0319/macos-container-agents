use crossterm::event::KeyCode;
use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::Style;
use ratatui::text::Line;
use ratatui::text::Span;
use ratatui::widgets::Clear;
use ratatui::widgets::Paragraph;
use ratatui::widgets::Widget;
use ratatui::widgets::Wrap;
use runhaven_core::ui_contracts::AuthDecisionData;
use runhaven_core::ui_contracts::DoctorCheckData;
use runhaven_core::ui_contracts::EgressDecisionData;
use runhaven_core::ui_contracts::RunHavenDiagnosticsData;
use runhaven_core::ui_contracts::RunHistorySummaryData;

use crate::key_hint;
use crate::render::renderable::Renderable;
use crate::style::accent_style;
use crate::style::boundary_style;
use crate::style::danger_style;
use crate::style::muted_but_readable_style;
use crate::style::safe_style;
use crate::style::selected_row_style;
use crate::style::warning_style;
use crate::tui::bottom_pane::render_menu_surface;

use super::ActiveRunsScreen;
use super::DiagnosticsScreen;
use super::HistoryScreen;
use super::LOG_CONFIRM_PHRASE;
use super::MvpScreen;
use super::PostRunOutcome;
use super::RunControlAction;
use super::RunControlScreen;
use super::RunControlState;
use super::RunHavenMvpView;
use super::RunLogsScreen;
use super::RunLogsState;

pub(super) fn render(view: &RunHavenMvpView, area: Rect, buf: &mut Buffer) {
    match &view.screen {
        MvpScreen::Launch => view.launch.render(area, buf),
        MvpScreen::ActiveRuns(screen) => render_active_runs(screen, area, buf),
        MvpScreen::RunLogs(screen) => render_run_logs(screen, area, buf),
        MvpScreen::RunControl(screen) => render_run_control(screen, area, buf),
        MvpScreen::History(screen) => render_history(screen, area, buf),
        MvpScreen::Diagnostics(screen) => render_diagnostics(screen, area, buf),
        MvpScreen::PostRun(outcome) => render_post_run(outcome, area, buf),
    }
}

pub(super) fn desired_height(view: &RunHavenMvpView, width: u16) -> u16 {
    match &view.screen {
        MvpScreen::Launch => view.launch.desired_height(width),
        MvpScreen::ActiveRuns(screen) => {
            paragraph(active_runs_lines(screen)).line_count(width.saturating_sub(4).max(1)) as u16
                + 2
        }
        MvpScreen::RunLogs(screen) => {
            paragraph(run_logs_lines(screen)).line_count(width.saturating_sub(4).max(1)) as u16 + 2
        }
        MvpScreen::RunControl(screen) => {
            paragraph(run_control_lines(screen)).line_count(width.saturating_sub(4).max(1)) as u16
                + 2
        }
        MvpScreen::History(screen) => {
            paragraph(history_lines(screen)).line_count(width.saturating_sub(4).max(1)) as u16 + 2
        }
        MvpScreen::Diagnostics(screen) => {
            paragraph(diagnostics_lines(screen)).line_count(width.saturating_sub(4).max(1)) as u16
                + 2
        }
        MvpScreen::PostRun(outcome) => {
            paragraph(post_run_lines(outcome)).line_count(width.saturating_sub(4).max(1)) as u16 + 2
        }
    }
}

fn render_active_runs(screen: &ActiveRunsScreen, area: Rect, buf: &mut Buffer) {
    render_panel(area, buf, active_runs_lines(screen));
}

fn active_runs_lines(screen: &ActiveRunsScreen) -> Vec<Line<'static>> {
    let mut lines = vec![header_line("Active runs"), tab_line(), Line::from("")];
    if screen.runs.runs.is_empty() {
        lines.push(Line::from("No active RunHaven runs found."));
        lines.push(Line::from(
            "Launch an agent or refresh after another terminal starts one.",
        ));
        return lines;
    }
    lines.push(Line::from(
        "Enter opens logs. s Stop. K Hard stop. x Repair marker. r Refresh.",
    ));
    lines.push(Line::from(""));
    for (idx, run) in screen.runs.runs.iter().enumerate() {
        let selected = idx == screen.selected_idx;
        lines.push(Line::from(vec![
            Span::styled(if selected { "> " } else { "  " }, accent_style()),
            Span::styled(
                run.run_id.clone(),
                if selected {
                    selected_row_style()
                } else {
                    boundary_style()
                },
            ),
            Span::raw("  "),
            Span::styled(run.profile.clone(), accent_style()),
            Span::raw("  "),
            Span::styled(run.network.clone(), network_style(&run.network)),
            Span::raw("  "),
            Span::styled(run.status.clone(), status_style(&run.status)),
        ]));
    }
    if let Some(run) = screen.selected_run() {
        lines.push(Line::from(""));
        lines.push(label_value("Profile", run.profile.clone(), accent_style()));
        lines.push(label_value("Run ID", run.run_id.clone(), boundary_style()));
        lines.push(label_value(
            "Container",
            run.container_name.clone(),
            muted_but_readable_style(),
        ));
        lines.push(label_value("State", run.state_volume.clone(), safe_style()));
        lines.push(label_value(
            "Session",
            run.session.clone(),
            muted_but_readable_style(),
        ));
        lines.push(label_value(
            "Started",
            run.timestamp.clone(),
            muted_but_readable_style(),
        ));
    }
    if let Some(notice) = &screen.notice {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(notice.clone(), warning_style())));
    }
    lines
}

fn render_run_control(screen: &RunControlScreen, area: Rect, buf: &mut Buffer) {
    render_panel(area, buf, run_control_lines(screen));
}

fn run_control_lines(screen: &RunControlScreen) -> Vec<Line<'static>> {
    let mut lines = vec![
        header_line(screen.action.title()),
        tab_line(),
        Line::from("This action only targets the selected RunHaven-owned container."),
        Line::from(""),
        label_value("Run ID", screen.run.run_id.clone(), boundary_style()),
        label_value("Profile", screen.run.profile.clone(), accent_style()),
        label_value(
            "Container",
            screen.run.container_name.clone(),
            muted_but_readable_style(),
        ),
        label_value(
            "Status",
            screen.run.status.clone(),
            status_style(&screen.run.status),
        ),
        Line::from(""),
    ];

    match &screen.state {
        RunControlState::Confirm { typed, notice } => {
            lines.push(Line::from(Span::styled(
                run_control_warning(screen.action),
                warning_style(),
            )));
            lines.push(Line::from(vec![
                Span::raw("Type "),
                Span::styled(screen.action.phrase(), selected_row_style()),
                Span::raw(", then press Enter."),
            ]));
            lines.push(label_value(
                "Typed",
                typed.clone(),
                muted_but_readable_style(),
            ));
            if let Some(notice) = notice {
                lines.push(Line::from(Span::styled(notice.clone(), warning_style())));
            }
        }
        RunControlState::Complete(result) => {
            lines.push(Line::from(Span::styled(
                result.message.clone(),
                result_style(&result.status),
            )));
            lines.push(label_value(
                "Result",
                result.status.clone(),
                result_style(&result.status),
            ));
            if let Some(code) = result.return_code {
                lines.push(label_value(
                    "Exit code",
                    code.to_string(),
                    if code == 0 {
                        safe_style()
                    } else {
                        warning_style()
                    },
                ));
            }
            if let Some(marker_removed) = result.marker_removed {
                lines.push(label_value(
                    "Marker",
                    if marker_removed { "removed" } else { "kept" },
                    if marker_removed {
                        safe_style()
                    } else {
                        warning_style()
                    },
                ));
            }
            lines.push(Line::from(""));
            lines.push(Line::from(
                "Press r to refresh active runs, or Esc to go back.",
            ));
        }
        RunControlState::Error(message) => {
            lines.push(Line::from(Span::styled(
                "Run control failed.",
                danger_style(),
            )));
            lines.push(Line::from(message.clone()));
            lines.push(Line::from(""));
            lines.push(Line::from(
                "Press r to refresh active runs, or Esc to go back.",
            ));
        }
    }
    lines
}

fn run_control_warning(action: RunControlAction) -> &'static str {
    match action {
        RunControlAction::Stop => {
            "Stop asks the container to exit cleanly. Work inside the agent may stop."
        }
        RunControlAction::Kill => {
            "Hard stop kills the container now. Unsaved work inside the agent may be lost."
        }
        RunControlAction::Repair => {
            "Repair checks whether the container still exists before changing the marker."
        }
    }
}

fn result_style(status: &str) -> Style {
    match status {
        "requested" | "removed" => safe_style(),
        "kept" => warning_style(),
        _ => danger_style(),
    }
}

fn render_run_logs(screen: &RunLogsScreen, area: Rect, buf: &mut Buffer) {
    render_panel(area, buf, run_logs_lines(screen));
}

fn run_logs_lines(screen: &RunLogsScreen) -> Vec<Line<'static>> {
    let mut lines = vec![
        header_line("Run logs"),
        Line::from(vec![
            Span::styled("Run ID  ", muted_but_readable_style()),
            Span::styled(screen.run.run_id.clone(), boundary_style()),
            Span::raw("  "),
            Span::styled("Profile  ", muted_but_readable_style()),
            Span::styled(screen.run.profile.clone(), accent_style()),
        ]),
        Line::from(""),
    ];

    match &screen.state {
        RunLogsState::Confirm { typed, notice } => {
            lines.push(Line::from(vec![Span::styled(
                "Raw container output can contain secrets or workspace content.",
                warning_style(),
            )]));
            lines.push(Line::from(vec![
                Span::raw("Type "),
                Span::styled(LOG_CONFIRM_PHRASE, selected_row_style()),
                Span::raw(", then press Enter to load a bounded snapshot."),
            ]));
            lines.push(label_value(
                "Typed",
                typed.clone(),
                muted_but_readable_style(),
            ));
            if let Some(notice) = notice {
                lines.push(Line::from(Span::styled(notice.clone(), warning_style())));
            }
        }
        RunLogsState::Loaded(snapshot) => {
            lines.push(label_value(
                "Captured",
                snapshot.captured_at.clone(),
                muted_but_readable_style(),
            ));
            lines.push(label_value(
                "Returned",
                format!("{} lines", snapshot.returned_lines),
                safe_style(),
            ));
            if snapshot.truncated {
                lines.push(Line::from(Span::styled(
                    "Output was truncated to the bounded snapshot size.",
                    warning_style(),
                )));
            }
            for warning in &snapshot.warnings {
                lines.push(Line::from(Span::styled(warning.clone(), warning_style())));
            }
            lines.push(Line::from(""));
            lines.push(Line::from(vec![Span::styled(
                "Snapshot",
                selected_row_style(),
            )]));
            if snapshot.text.is_empty() {
                lines.push(Line::from("(no output returned)"));
            } else {
                for line in snapshot.text.lines().take(120) {
                    lines.push(Line::from(line.to_string()));
                }
            }
        }
        RunLogsState::Error(message) => {
            lines.push(Line::from(Span::styled(
                "Could not load run logs.",
                danger_style(),
            )));
            lines.push(Line::from(message.clone()));
        }
    }
    lines
}

fn render_history(screen: &HistoryScreen, area: Rect, buf: &mut Buffer) {
    render_panel(area, buf, history_lines(screen));
}

fn history_lines(screen: &HistoryScreen) -> Vec<Line<'static>> {
    let mut lines = vec![
        header_line("Run history"),
        tab_line(),
        Line::from("Recent run records. Host workspace paths are hidden in the TUI."),
        Line::from(""),
    ];
    match &screen.result {
        Ok(history) if history.runs.is_empty() => {
            lines.push(Line::from("No RunHaven run records found."));
            lines.push(Line::from(
                "Launch an agent, then return here after it exits.",
            ));
        }
        Ok(history) => {
            for (idx, run) in history.runs.iter().enumerate().take(10) {
                let selected = idx == screen.selected_idx;
                lines.push(history_row(run, selected));
            }
            if let Some(run) = screen.selected_run() {
                append_history_detail(&mut lines, run);
            }
        }
        Err(error) => {
            lines.push(Line::from(Span::styled(
                "Could not load run history.",
                danger_style(),
            )));
            lines.push(Line::from(error.clone()));
        }
    }
    lines
}

fn history_row(run: &RunHistorySummaryData, selected: bool) -> Line<'static> {
    Line::from(vec![
        Span::styled(if selected { "> " } else { "  " }, accent_style()),
        Span::styled(
            run.run_id.clone(),
            if selected {
                selected_row_style()
            } else {
                boundary_style()
            },
        ),
        Span::raw("  "),
        Span::styled(run.profile.clone(), accent_style()),
        Span::raw("  "),
        Span::styled(run.network.clone(), network_style(&run.network)),
        Span::raw("  "),
        Span::styled(run.status.clone(), status_style(&run.status)),
        Span::raw("  return="),
        Span::styled(format_return_code(run), muted_but_readable_style()),
    ])
}

fn append_history_detail(lines: &mut Vec<Line<'static>>, run: &RunHistorySummaryData) {
    lines.push(Line::from(""));
    lines.push(label_value("Run ID", run.run_id.clone(), boundary_style()));
    lines.push(label_value(
        "Started",
        run.started_at.clone(),
        muted_but_readable_style(),
    ));
    lines.push(label_value(
        "Finished",
        run.finished_at.clone(),
        muted_but_readable_style(),
    ));
    lines.push(label_value(
        "Scope",
        run.workspace_scope.clone(),
        safe_style(),
    ));
    lines.push(label_value("State", run.state_volume.clone(), safe_style()));
    lines.push(label_value(
        "Session",
        run.session.clone(),
        muted_but_readable_style(),
    ));
    lines.push(label_value(
        "Provider",
        format!(
            "allowed {} denied {}",
            run.provider_allowed, run.provider_denied
        ),
        if run.provider_denied == 0 {
            safe_style()
        } else {
            warning_style()
        },
    ));
    lines.push(label_value(
        "Auth",
        format!("allowed {} denied {}", run.auth_allowed, run.auth_denied),
        if run.auth_denied == 0 {
            safe_style()
        } else {
            warning_style()
        },
    ));
    lines.push(label_value(
        "Cleanup",
        run.cleanup_provider_network.clone(),
        muted_but_readable_style(),
    ));
    lines.push(label_value(
        "Git",
        run.git_summary.clone(),
        muted_but_readable_style(),
    ));
    if let Some(branch) = &run.worktree_branch {
        lines.push(label_value("Worktree", branch.clone(), warning_style()));
    }
    lines.push(Line::from(""));
    lines.push(label_value(
        "Review",
        run.review_command.clone(),
        boundary_style(),
    ));
}

fn format_return_code(run: &RunHistorySummaryData) -> String {
    run.return_code
        .map(|code| code.to_string())
        .unwrap_or_else(|| "-".to_string())
}

fn render_diagnostics(screen: &DiagnosticsScreen, area: Rect, buf: &mut Buffer) {
    render_panel(area, buf, diagnostics_lines(screen));
}

fn diagnostics_lines(screen: &DiagnosticsScreen) -> Vec<Line<'static>> {
    let mut lines = vec![
        header_line("Diagnostics"),
        tab_line(),
        Line::from("Preflight status, auth metadata, and recent broker/proxy decisions."),
        Line::from(""),
    ];
    match &screen.result {
        Ok(data) => append_diagnostics_data(&mut lines, data),
        Err(error) => {
            lines.push(Line::from(Span::styled(
                "Could not load diagnostics.",
                danger_style(),
            )));
            lines.push(Line::from(error.clone()));
        }
    }
    lines
}

fn append_diagnostics_data(lines: &mut Vec<Line<'static>>, data: &RunHavenDiagnosticsData) {
    append_doctor_lines(lines, &data.doctor_checks);
    lines.push(label_value(
        "Auth",
        data.auth_status.status.clone(),
        safe_style(),
    ));
    lines.push(label_value(
        "Runtime",
        data.auth_status.runtime.clone(),
        muted_but_readable_style(),
    ));
    lines.push(Line::from(""));
    lines.push(Line::from(vec![Span::styled(
        "Auth profiles",
        selected_row_style(),
    )]));
    for profile in data.auth_status.profiles.iter().take(8) {
        lines.push(Line::from(format!("{}  {}", profile.name, profile.status)));
    }
    append_egress_lines(lines, &data.egress_log);
    append_auth_lines(lines, &data.auth_log);
}

fn append_doctor_lines(lines: &mut Vec<Line<'static>>, checks: &[DoctorCheckData]) {
    lines.push(Line::from(vec![Span::styled(
        "Preflight",
        selected_row_style(),
    )]));
    if checks.is_empty() {
        lines.push(Line::from("No preflight checks returned."));
        lines.push(Line::from(""));
        return;
    }
    let passed = checks.iter().filter(|check| check.ok).count();
    if passed > 0 {
        lines.push(Line::from(vec![
            Span::styled("ok", safe_style()),
            Span::raw("  "),
            Span::styled(check_count_label(passed), muted_but_readable_style()),
        ]));
    }

    let failed: Vec<_> = checks.iter().filter(|check| !check.ok).collect();
    if failed.is_empty() {
        lines.push(Line::from(""));
        return;
    }

    for check in failed.iter().take(6) {
        lines.push(Line::from(vec![
            Span::styled("fix", warning_style()),
            Span::raw("  "),
            Span::styled(check.name.clone(), boundary_style()),
            Span::raw("  "),
            Span::styled(check.detail.clone(), muted_but_readable_style()),
        ]));
        lines.push(Line::from(vec![
            Span::raw("    "),
            Span::styled(check.remedy.clone(), warning_style()),
        ]));
    }
    if failed.len() > 6 {
        lines.push(Line::from(vec![
            Span::styled("fix", warning_style()),
            Span::raw("  "),
            Span::styled(
                format!("{} more checks need attention.", failed.len() - 6),
                warning_style(),
            ),
        ]));
    }
    lines.push(Line::from(""));
}

fn check_count_label(count: usize) -> String {
    if count == 1 {
        "1 check passed".to_string()
    } else {
        format!("{count} checks passed")
    }
}

fn append_egress_lines(lines: &mut Vec<Line<'static>>, entries: &[EgressDecisionData]) {
    lines.push(Line::from(""));
    lines.push(Line::from(vec![Span::styled(
        "Provider egress",
        selected_row_style(),
    )]));
    if entries.is_empty() {
        lines.push(Line::from("No provider egress decisions found."));
        return;
    }
    for entry in entries.iter().take(8) {
        lines.push(Line::from(format!(
            "{}  {}  {}:{}  count={}  {}",
            entry.profile, entry.decision, entry.host, entry.port, entry.count, entry.reason
        )));
    }
}

fn append_auth_lines(lines: &mut Vec<Line<'static>>, entries: &[AuthDecisionData]) {
    lines.push(Line::from(""));
    lines.push(Line::from(vec![Span::styled(
        "Auth broker",
        selected_row_style(),
    )]));
    if entries.is_empty() {
        lines.push(Line::from("No auth broker decisions found."));
        return;
    }
    for entry in entries.iter().take(8) {
        let status = entry
            .upstream_status
            .map(|status| status.to_string())
            .unwrap_or_else(|| "-".to_string());
        lines.push(Line::from(format!(
            "{}  {}  {} {}  upstream={}  count={}",
            entry.profile, entry.decision, entry.method, entry.path, status, entry.count
        )));
    }
}

fn render_post_run(outcome: &PostRunOutcome, area: Rect, buf: &mut Buffer) {
    render_panel(area, buf, post_run_lines(outcome));
}

fn post_run_lines(outcome: &PostRunOutcome) -> Vec<Line<'static>> {
    let mut lines = vec![
        header_line("Run finished"),
        Line::from("The terminal is back in RunHaven."),
        Line::from(""),
        label_value("Agent", outcome.plan.profile_name.clone(), accent_style()),
        label_value(
            "Exit",
            outcome.exit_code.to_string(),
            exit_style(outcome.exit_code, outcome.error.as_ref()),
        ),
        label_value(
            "Network",
            outcome.plan.network.mode.clone(),
            network_style(&outcome.plan.network.mode),
        ),
        label_value("Auth scope", outcome.plan.auth_scope.clone(), safe_style()),
        label_value("Boundary", "/workspace only", boundary_style()),
        label_value("State", outcome.plan.state_volume.clone(), safe_style()),
    ];
    if let Some(error) = &outcome.error {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled("Launch error", danger_style())));
        lines.push(Line::from(error.clone()));
    }
    lines.push(Line::from(""));
    lines.push(Line::from(
        "Enter starts another launch. 2 shows active runs. 3 shows diagnostics. q quits.",
    ));
    lines
}

fn render_panel(area: Rect, buf: &mut Buffer, lines: Vec<Line<'static>>) {
    Clear.render(area, buf);
    let content = render_menu_surface(area, buf);
    paragraph(lines).render(content, buf);
}

fn paragraph(lines: Vec<Line<'static>>) -> Paragraph<'static> {
    Paragraph::new(lines).wrap(Wrap { trim: false })
}

fn header_line(title: &'static str) -> Line<'static> {
    Line::from(vec![
        Span::styled("RunHaven", selected_row_style()),
        Span::raw(format!(" v{}  ", env!("CARGO_PKG_VERSION"))),
        Span::styled(title, boundary_style()),
    ])
}

fn tab_line() -> Line<'static> {
    Line::from(vec![
        key_hint::plain(KeyCode::Char('1')).into(),
        Span::raw(" Launch  "),
        key_hint::plain(KeyCode::Char('2')).into(),
        Span::raw(" Runs  "),
        key_hint::plain(KeyCode::Char('3')).into(),
        Span::raw(" Diagnostics  "),
        key_hint::plain(KeyCode::Char('h')).into(),
        Span::raw(" History"),
    ])
}

fn label_value(label: &'static str, value: impl Into<String>, value_style: Style) -> Line<'static> {
    Line::from(vec![
        Span::styled(format!("{label:<12}"), muted_but_readable_style()),
        Span::styled(value.into(), value_style),
    ])
}

fn network_style(network: &str) -> Style {
    if network == "internet" {
        warning_style()
    } else {
        safe_style()
    }
}

fn status_style(status: &str) -> Style {
    match status {
        "running" => safe_style(),
        "stop-requested" | "kill-requested" => warning_style(),
        _ => muted_but_readable_style(),
    }
}

pub(super) fn exit_style(exit_code: i32, error: Option<&String>) -> Style {
    if exit_code == 0 && error.is_none() {
        safe_style()
    } else {
        warning_style()
    }
}
