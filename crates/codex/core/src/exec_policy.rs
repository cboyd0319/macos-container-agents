use std::fmt;
use std::path::PathBuf;

use codex_config::ConfigLayerStack;
use codex_execpolicy::Policy;

#[derive(Debug)]
pub enum ExecPolicyError {
    ReadFile {
        path: PathBuf,
        source: std::io::Error,
    },
    ParsePolicy {
        path: PathBuf,
        source: codex_execpolicy::Error,
    },
    ReadDir {
        path: PathBuf,
        source: std::io::Error,
    },
}

impl fmt::Display for ExecPolicyError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&format_exec_policy_error_with_source(self))
    }
}

impl std::error::Error for ExecPolicyError {}

pub async fn check_execpolicy_for_warnings(
    _config_stack: &ConfigLayerStack,
) -> Result<Option<ExecPolicyError>, ExecPolicyError> {
    Ok(None)
}

pub fn format_exec_policy_error_with_source(error: &ExecPolicyError) -> String {
    match error {
        ExecPolicyError::ParsePolicy { path, source } => {
            format!(
                "failed to parse execpolicy file `{}`: {source}",
                path.display()
            )
        }
        ExecPolicyError::ReadFile { path, source } => {
            format!(
                "failed to read execpolicy file `{}`: {source}",
                path.display()
            )
        }
        ExecPolicyError::ReadDir { path, source } => {
            format!(
                "failed to read execpolicy directory `{}`: {source}",
                path.display()
            )
        }
    }
}

pub async fn load_exec_policy(_config_stack: &ConfigLayerStack) -> Result<Policy, ExecPolicyError> {
    Ok(Policy::empty())
}
