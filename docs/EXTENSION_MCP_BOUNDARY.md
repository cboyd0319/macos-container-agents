# Extension And MCP Boundary

RunHaven does not currently enable MCP servers, editor extensions, or plugin
marketplaces inside managed agent runs. This document is the policy gate for any
future support.

## Default Policy

- Deny by default. No MCP server, extension, socket, credential helper, or host
  service is exposed unless the user explicitly enables it for a run.
- Prefer container-side tools. If an MCP server can run inside the agent
  container without host credentials or host sockets, use that shape first.
- Do not mount the macOS home directory, browser profiles, raw SSH keys, cloud
  credential folders, or provider credential caches to support an extension.
- Do not pass arbitrary host environment variables. Use named `--env NAME`
  passthrough only when the user intentionally accepts that narrower risk.
- Project config can request less access, but it cannot silently widen host
  filesystem, network, credential, or process access.
- Provider egress policy still applies. Extensions do not bypass
  `--network internal` or `--network provider` boundaries.

## Required Design Checks

Any implementation must define:

- the exact command, socket, file, network host, or environment variable exposed
  to the guest;
- whether the exposed surface is read-only, read-write, or execute-capable;
- which profile and session can use it;
- how the user sees and approves the access before launch;
- how run records describe the enabled surface without printing secrets;
- how cleanup happens after the run;
- focused tests for denied-by-default behavior and each explicit allow path.

## Non-Goals

- Host-wide extension discovery.
- Silent import of editor, browser, or shell configuration.
- Automatic credential sharing with MCP servers.
- Long-lived host daemons started by project files.
- Broad allowlists such as "all local services" or "all GitHub endpoints"
  without a source-backed, enforceable policy.

## Minimum Acceptable Flow

1. `runhaven plan` prints the exact extension or MCP access that would be
   granted.
2. The run requires an explicit opt-in flag or approved profile policy.
3. Runtime setup fails closed if the requested host path, socket, or network
   boundary cannot be verified.
4. Run records capture that extension/MCP access was enabled without storing
   prompts, payloads, credential values, or host secrets.
