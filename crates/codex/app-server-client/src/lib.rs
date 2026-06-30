//! Reduced `codex-app-server-client` compatibility boundary for TUI vendoring.
//!
//! Upstream Codex exposes `codex_app_server_client::legacy_core` so TUI modules
//! can keep legacy config imports while app-server APIs move behind protocol
//! calls. RunHaven keeps that original package and crate path, but omits the
//! app-server transport until those host-reaching boundaries are designed.

pub mod legacy_core {
    pub use codex_core::check_execpolicy_for_warnings;
    pub use codex_core::format_exec_policy_error_with_source;

    pub mod config {
        pub use codex_core::config::*;

        pub mod edit {
            pub use codex_core::config::edit::*;
        }
    }
}

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

    #[test]
    fn reduced_manifest_does_not_depend_on_app_server_runtime_crates() {
        let manifest = include_str!("../Cargo.toml");

        for forbidden in [
            "codex-app-server",
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
                "reduced codex-app-server-client must not depend on backend/runtime crate {forbidden}"
            );
        }
    }
}
