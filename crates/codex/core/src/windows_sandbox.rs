use codex_protocol::config_types::WindowsSandboxLevel;
use toml::Value as TomlValue;

/// Config-facing subset of upstream Codex's Windows sandbox helper.
pub trait WindowsSandboxLevelExt {
    fn from_config(config: &crate::config::Config) -> Self;
}

impl WindowsSandboxLevelExt for WindowsSandboxLevel {
    fn from_config(config: &crate::config::Config) -> Self {
        config
            .windows_sandbox_level
            .unwrap_or(WindowsSandboxLevel::Disabled)
    }
}

pub fn resolve_windows_sandbox_mode(
    config: &codex_config::config_toml::ConfigToml,
) -> Option<codex_config::types::WindowsSandboxModeToml> {
    config.windows.as_ref().and_then(|windows| windows.sandbox)
}

pub fn resolve_windows_sandbox_private_desktop(
    config: &codex_config::config_toml::ConfigToml,
) -> bool {
    config
        .windows
        .as_ref()
        .and_then(|windows| windows.sandbox_private_desktop)
        .unwrap_or(true)
}

#[allow(dead_code)]
pub fn legacy_windows_sandbox_mode_from_entries(
    entries: &std::collections::BTreeMap<String, TomlValue>,
) -> Option<codex_config::types::WindowsSandboxModeToml> {
    if entries
        .get("elevated_windows_sandbox")
        .and_then(TomlValue::as_bool)
        .unwrap_or(false)
    {
        return Some(codex_config::types::WindowsSandboxModeToml::Elevated);
    }

    let enabled = entries
        .get("experimental_windows_sandbox")
        .or_else(|| entries.get("enable_experimental_windows_sandbox"))
        .and_then(TomlValue::as_bool)
        .unwrap_or(false);
    enabled.then_some(codex_config::types::WindowsSandboxModeToml::Unelevated)
}
