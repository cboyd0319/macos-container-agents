#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct NetworkProxySpec {
    socks_enabled: bool,
}

impl NetworkProxySpec {
    pub fn disabled() -> Self {
        Self {
            socks_enabled: false,
        }
    }

    pub fn socks_enabled(&self) -> bool {
        self.socks_enabled
    }
}
