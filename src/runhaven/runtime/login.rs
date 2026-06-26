//! `runhaven login <agent>`: acquire a provider login once, host-side, so runs
//! reuse it without re-authenticating.
//!
//! Today this implements the Claude path. Claude Code has no in-container
//! device-code login at the pinned version, so an in-sandbox login requires
//! pasting a code back. Instead `runhaven login claude` runs Anthropic's
//! official `claude setup-token` on the host (where the browser and localhost
//! callback work), stores the resulting OAuth token `0600` in the RunHaven
//! cache, and later runs inject it into the sandbox env at run time only. The
//! token is a usable credential, so this is an explicit, warned opt-in: the
//! guest then holds a token, and provider-network egress keeps it from leaving
//! the provider's hosts.

use std::io::{Read, Write};
use std::process::{Command, Stdio};

use anyhow::{Context, Result, bail};

use crate::doctor::find_on_path;
use crate::paths::{create_private_file, ensure_private_parent, oauth_token_path};
use crate::plans::AgentRunPlan;

/// Agents whose login RunHaven can store host-side as an OAuth token and inject
/// into the guest at run time. Maps the agent to the env var its CLI reads.
fn token_env_var(agent: &str) -> Option<&'static str> {
    match agent {
        "claude" => Some("CLAUDE_CODE_OAUTH_TOKEN"),
        _ => None,
    }
}

pub fn login(agent: &str) -> Result<i32> {
    match agent {
        "claude" => login_claude(),
        other => bail!(
            "runhaven login does not yet support {other:?}. Run the agent and log in inside the sandbox, or use --api-key-broker-env for an API key."
        ),
    }
}

pub fn logout(agent: &str) -> Result<i32> {
    let path = oauth_token_path(agent);
    if path.exists() {
        std::fs::remove_file(&path)
            .with_context(|| format!("could not remove stored login: {}", path.display()))?;
        eprintln!("Cleared the stored {agent} login.");
    } else {
        eprintln!("No stored {agent} login to clear.");
    }
    Ok(0)
}

fn login_claude() -> Result<i32> {
    // setup-token runs on the host, where the browser and localhost callback work.
    let claude = find_on_path("claude").ok_or_else(|| {
        anyhow::anyhow!(
            "runhaven login claude needs Claude Code installed on your host to run `claude setup-token`. Install it (for example `npm install -g @anthropic-ai/claude-code`) or log in inside the sandbox with `runhaven run claude`."
        )
    })?;
    eprintln!(
        "Running `claude setup-token` on the host. Approve the login in your browser. The token is stored only for RunHaven and is injected into the sandbox at run time, never written to your `~/.claude`."
    );
    // Capture stdout (the token); inherit stderr/stdin so the browser flow and
    // any prompts work normally.
    let output = Command::new(&claude)
        .arg("setup-token")
        .stdin(Stdio::inherit())
        .stderr(Stdio::inherit())
        .stdout(Stdio::piped())
        .output()
        .with_context(|| format!("could not run {claude} setup-token"))?;
    if !output.status.success() {
        bail!("claude setup-token did not succeed; nothing was stored");
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let token = extract_token(&stdout).ok_or_else(|| {
        anyhow::anyhow!("could not find a token in `claude setup-token` output; nothing was stored")
    })?;
    store_token("claude", &token)?;
    eprintln!(
        "Stored your Claude login. `runhaven run claude` now injects it into the sandbox env (a usable token; provider-network egress keeps it from leaving Anthropic's hosts). Clear it with `runhaven login claude --clear`."
    );
    Ok(0)
}

/// Take the OAuth token from `claude setup-token` output: the last non-empty
/// line that looks like an Anthropic OAuth token.
fn extract_token(stdout: &str) -> Option<String> {
    stdout
        .lines()
        .map(str::trim)
        .rfind(|line| line.starts_with("sk-ant-") && line.len() > 20)
        .map(str::to_string)
}

fn store_token(agent: &str, token: &str) -> Result<()> {
    let path = oauth_token_path(agent);
    ensure_private_parent(&path)?;
    let mut file = create_private_file(&path)
        .with_context(|| format!("could not write login store: {}", path.display()))?;
    file.write_all(token.as_bytes())?;
    file.write_all(b"\n")?;
    Ok(())
}

fn read_token(agent: &str) -> Option<String> {
    let mut file = std::fs::File::open(oauth_token_path(agent)).ok()?;
    let mut contents = String::new();
    file.read_to_string(&mut contents).ok()?;
    let token = contents.trim();
    (!token.is_empty()).then(|| token.to_string())
}

/// The token to inject for a run, if the agent has a stored login. Returns the
/// env var name and value. The value is set on the run Command's environment
/// (never on the argv or in the printed plan) and forwarded into the guest with
/// a name-only `--env`.
pub fn run_token_injection(plan: &AgentRunPlan) -> Option<(String, String)> {
    let env = token_env_var(&plan.profile_name)?;
    let token = read_token(&plan.profile_name)?;
    Some((env.to_string(), token))
}

/// Insert a name-only `--env NAME` for the injected token before the image, so
/// the guest inherits the value from the run Command's environment.
pub fn with_token_env(command: &[String], image: &str, env_name: &str) -> Vec<String> {
    let image_index = command
        .iter()
        .position(|arg| arg == image)
        .expect("image in command");
    let mut result = command[..image_index].to_vec();
    result.extend(["--env".to_string(), env_name.to_string()]);
    result.extend(command[image_index..].to_vec());
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_token_takes_the_anthropic_oauth_token_line() {
        // Obvious placeholder, not a real token; only the `sk-ant-` prefix and
        // length matter to the parser.
        let placeholder = "sk-ant-NOT-A-REAL-TOKEN-placeholder";
        let out = format!("Starting login...\n{placeholder}\n");
        assert_eq!(extract_token(&out).as_deref(), Some(placeholder));
        assert!(extract_token("no token here\n").is_none());
    }

    #[test]
    fn with_token_env_inserts_name_only_env_before_image() {
        let command = vec![
            "container".to_string(),
            "run".to_string(),
            "--name".to_string(),
            "runhaven-claude-run".to_string(),
            "runhaven/claude:0.1.0".to_string(),
            "claude".to_string(),
        ];
        let result = with_token_env(&command, "runhaven/claude:0.1.0", "CLAUDE_CODE_OAUTH_TOKEN");
        let env_index = result
            .windows(2)
            .position(|w| w == ["--env", "CLAUDE_CODE_OAUTH_TOKEN"])
            .expect("env injected");
        let image_index = result
            .iter()
            .position(|arg| arg == "runhaven/claude:0.1.0")
            .expect("image present");
        // The name-only env appears before the image, and the value is never on
        // the command line.
        assert!(env_index < image_index);
        assert!(!result.iter().any(|arg| arg.contains("sk-ant-")));
    }
}
