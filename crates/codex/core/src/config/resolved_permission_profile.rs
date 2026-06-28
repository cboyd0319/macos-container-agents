pub use codex_protocol::models::ActivePermissionProfile;
pub use codex_protocol::models::PermissionProfile;
pub use codex_utils_absolute_path::AbsolutePathBuf;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PermissionProfileSnapshot {
    permission_profile: PermissionProfile,
    active_permission_profile: Option<ActivePermissionProfile>,
    profile_workspace_roots: Vec<AbsolutePathBuf>,
}

impl PermissionProfileSnapshot {
    pub fn legacy(permission_profile: PermissionProfile) -> Self {
        Self {
            permission_profile,
            active_permission_profile: None,
            profile_workspace_roots: Vec::new(),
        }
    }

    pub fn active(
        permission_profile: PermissionProfile,
        active_permission_profile: ActivePermissionProfile,
    ) -> Self {
        Self::active_with_profile_workspace_roots(
            permission_profile,
            active_permission_profile,
            Vec::new(),
        )
    }

    pub fn active_with_profile_workspace_roots(
        permission_profile: PermissionProfile,
        active_permission_profile: ActivePermissionProfile,
        profile_workspace_roots: Vec<AbsolutePathBuf>,
    ) -> Self {
        Self {
            permission_profile,
            active_permission_profile: Some(active_permission_profile),
            profile_workspace_roots,
        }
    }

    pub fn from_session_snapshot(
        permission_profile: PermissionProfile,
        active_permission_profile: Option<ActivePermissionProfile>,
    ) -> Self {
        Self {
            permission_profile,
            active_permission_profile,
            profile_workspace_roots: Vec::new(),
        }
    }

    pub fn permission_profile(&self) -> &PermissionProfile {
        &self.permission_profile
    }

    pub fn active_permission_profile(&self) -> Option<ActivePermissionProfile> {
        self.active_permission_profile.clone()
    }

    pub fn profile_workspace_roots(&self) -> &[AbsolutePathBuf] {
        &self.profile_workspace_roots
    }
}
