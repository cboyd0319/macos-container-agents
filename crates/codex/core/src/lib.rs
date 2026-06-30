//! Reduced `codex-core` compatibility authority for RunHaven TUI vendoring.
//!
//! This crate keeps the original Codex package and crate name, but only exposes
//! the config-facing surface needed before RunHaven promotes the native Codex
//! `App`/`BottomPane` path. Host-reaching Codex backend modules stay absent
//! until RunHaven gives each boundary a security design.

#![deny(clippy::print_stdout, clippy::print_stderr)]

pub mod config;
mod exec_policy;
pub mod unified_exec;
pub(crate) mod utils;
pub mod windows_sandbox;

pub use exec_policy::check_execpolicy_for_warnings;
pub use exec_policy::format_exec_policy_error_with_source;
pub use exec_policy::load_exec_policy;
pub use utils::path_utils;

#[cfg(test)]
mod tests {
    fn dependency_declared(manifest: &str, package: &str) -> bool {
        manifest.lines().map(str::trim).any(|line| {
            line.starts_with(package)
                && line
                    .strip_prefix(package)
                    .is_some_and(|rest| rest.trim_start().starts_with('='))
        })
    }

    fn module_declared(lib: &str, module: &str) -> bool {
        let private_decl = format!("mod {module};");
        let crate_decl = format!("pub(crate) mod {module};");
        let public_decl = format!("pub mod {module};");
        lib.lines()
            .map(str::trim)
            .any(|line| line == private_decl || line == crate_decl || line == public_decl)
    }

    #[test]
    fn reduced_manifest_does_not_depend_on_backend_runtime_crates() {
        let manifest = include_str!("../Cargo.toml");

        for forbidden in [
            "codex-app-server",
            "codex-app-server-client",
            "codex-login",
            "codex-mcp",
            "codex-hooks",
            "codex-tools",
            "codex-rollout",
            "codex-state",
            "codex-model-provider",
            "codex-exec-server",
            "codex-file-system",
            "codex-thread-store",
            "codex-rmcp-client",
        ] {
            assert!(
                !dependency_declared(manifest, forbidden),
                "reduced codex-core must not depend on backend/runtime crate {forbidden}"
            );
        }
    }

    #[test]
    fn reduced_module_graph_stays_config_only() {
        let lib = include_str!("lib.rs");

        for forbidden in [
            "session",
            "app_server",
            "exec",
            "mcp",
            "shell",
            "spawn",
            "thread_manager",
            "tools",
            "rollout",
            "state",
            "client",
        ] {
            assert!(
                !module_declared(lib, forbidden),
                "reduced codex-core must not expose backend/runtime module {forbidden:?}"
            );
        }
    }
}
