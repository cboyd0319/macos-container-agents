use std::io::IsTerminal;

fn main() {
    std::process::exit(main_entry());
}

fn main_entry() -> i32 {
    if std::env::args_os().nth(1).is_none() && should_launch_tui() {
        return match runhaven_tui::run() {
            Ok(code) => code,
            Err(error) => {
                eprintln!("runhaven: {error}");
                2
            }
        };
    }

    runhaven_cli::main_entry()
}

/// The TUI is the default only when both stdin and stdout are a terminal, so
/// piped or redirected invocations keep the CLI help-on-no-subcommand behavior.
fn should_launch_tui() -> bool {
    std::io::stdin().is_terminal() && std::io::stdout().is_terminal()
}
