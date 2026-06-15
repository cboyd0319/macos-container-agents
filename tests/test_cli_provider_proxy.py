from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from runhaven.cli import main
from runhaven.egress import ProxyDecision


class CliProviderProxyTests(unittest.TestCase):
    def test_provider_network_plan_prints_allowlist_summary(self) -> None:
        with TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["plan", "codex", "--workspace", directory, "--network", "provider"])

        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("provider allowlist", text)
        self.assertIn("api.openai.com", text)
        self.assertIn("chatgpt.com", text)
        self.assertIn("RunHaven injects proxy environment variables at runtime", text)

    def test_provider_run_injects_proxy_environment_and_cleans_network(self) -> None:
        with TemporaryDirectory() as directory:
            fake_proxy = Mock()
            fake_proxy.server_address = ("0.0.0.0", 49321)
            fake_proxy.denied_connect_targets.return_value = ()
            fake_proxy.policy_decisions.return_value = (
                ProxyDecision(
                    host="api.example.com",
                    port=443,
                    decision="allowed",
                    reason="allowed",
                    matched_rule="example.com",
                    count=2,
                ),
            )
            thread = Mock()
            network_info = Mock(ipv4_gateway="192.168.130.1", ipv4_subnet="192.168.130.0/24")
            error_output = io.StringIO()
            with (
                redirect_stderr(error_output),
                patch.dict("os.environ", {"RUNHAVEN_CACHE_HOME": directory}, clear=False),
                patch("runhaven.cli.require_container_cli"),
                patch("runhaven.cli.run_preflight") as preflight,
                patch(
                    "runhaven.cli.inspect_internal_network",
                    return_value=network_info,
                ) as inspect,
                patch("runhaven.cli.create_provider_proxy", return_value=fake_proxy) as proxy,
                patch("runhaven.cli.threading.Thread", return_value=thread),
                patch("runhaven.cli.delete_container_network") as delete_network,
                patch("runhaven.cli.subprocess.call", return_value=9) as call,
            ):
                code = main(
                    [
                        "run",
                        "shell",
                        "--workspace",
                        directory,
                        "--network",
                        "provider",
                        "--provider-host",
                        "example.com",
                        "--env",
                        "HTTPS_PROXY",
                        "--tty",
                        "never",
                        "--",
                        "/bin/true",
                    ]
                )

        self.assertEqual(code, 9)
        self.assertEqual(preflight.call_count, 3)
        provider_network = preflight.call_args_list[-1].args[0][-1]
        inspect.assert_called_once_with(provider_network)
        proxy.assert_called_once()
        self.assertEqual(proxy.call_args.args[0].allowed_hosts, ("example.com",))
        self.assertEqual(proxy.call_args.args[1].ipv4_gateway, "192.168.130.1")
        thread.start.assert_called_once()
        fake_proxy.shutdown.assert_called_once()
        fake_proxy.server_close.assert_called_once()
        thread.join.assert_called_once()
        delete_network.assert_called_once_with(provider_network)
        command = call.call_args.args[0]
        self.assertIn("HTTPS_PROXY=http://192.168.130.1:49321", command)
        self.assertIn("HTTP_PROXY=http://192.168.130.1:49321", command)
        self.assertIn("ALL_PROXY=http://192.168.130.1:49321", command)
        https_proxy_values = [
            value for value in command if value == "HTTPS_PROXY" or value.startswith("HTTPS_PROXY=")
        ]
        self.assertEqual(https_proxy_values[-1], "HTTPS_PROXY=http://192.168.130.1:49321")
        self.assertEqual(command[-1], "/bin/true")

    def test_provider_run_prints_blocked_host_summary(self) -> None:
        with TemporaryDirectory() as directory:
            fake_proxy = Mock()
            fake_proxy.server_address = ("0.0.0.0", 49321)
            fake_proxy.denied_connect_targets.return_value = (
                ("blocked.example.com", 443),
                ("1.1.1.1", 443),
            )
            fake_proxy.policy_decisions.return_value = (
                ProxyDecision(
                    host="blocked.example.com",
                    port=443,
                    decision="denied",
                    reason="not-in-allowlist",
                    matched_rule="",
                    count=3,
                ),
                ProxyDecision(
                    host="1.1.1.1",
                    port=443,
                    decision="denied",
                    reason="ip-literal",
                    matched_rule="",
                    count=1,
                ),
            )
            thread = Mock()
            network_info = Mock(ipv4_gateway="192.168.130.1", ipv4_subnet="192.168.130.0/24")
            error_output = io.StringIO()
            with (
                redirect_stderr(error_output),
                patch.dict("os.environ", {"RUNHAVEN_CACHE_HOME": directory}, clear=False),
                patch("runhaven.cli.require_container_cli"),
                patch("runhaven.cli.run_preflight"),
                patch("runhaven.cli.inspect_internal_network", return_value=network_info),
                patch("runhaven.cli.create_provider_proxy", return_value=fake_proxy),
                patch("runhaven.cli.threading.Thread", return_value=thread),
                patch("runhaven.cli.delete_container_network"),
                patch("runhaven.cli.subprocess.call", return_value=0),
            ):
                code = main(
                    [
                        "run",
                        "shell",
                        "--workspace",
                        directory,
                        "--network",
                        "provider",
                        "--provider-host",
                        "example.com",
                        "--tty",
                        "never",
                        "--",
                        "/bin/true",
                    ]
                )

        self.assertEqual(code, 0)
        text = error_output.getvalue()
        self.assertIn("RunHaven provider proxy blocked", text)
        self.assertIn("4 CONNECT requests across 2 target(s)", text)
        self.assertIn("Run id:", text)
        self.assertIn("blocked.example.com:443", text)
        self.assertIn("count=3", text)
        self.assertIn("reason=not-in-allowlist", text)
        self.assertIn("runhaven why host blocked.example.com --agent shell", text)
        self.assertIn("1.1.1.1:443", text)
        self.assertIn("IP literal targets cannot be allowed", text)
        self.assertIn("runhaven egress log --limit 20", text)

    def test_provider_run_writes_policy_log(self) -> None:
        with TemporaryDirectory() as directory:
            fake_proxy = Mock()
            fake_proxy.server_address = ("0.0.0.0", 49321)
            fake_proxy.denied_connect_targets.return_value = ()
            fake_proxy.policy_decisions.return_value = (
                ProxyDecision(
                    host="api.example.com",
                    port=443,
                    decision="allowed",
                    reason="allowed",
                    matched_rule="example.com",
                    count=2,
                ),
                ProxyDecision(
                    host="blocked.example.com",
                    port=443,
                    decision="denied",
                    reason="not-in-allowlist",
                    matched_rule="",
                    count=1,
                ),
            )
            thread = Mock()
            network_info = Mock(ipv4_gateway="192.168.130.1", ipv4_subnet="192.168.130.0/24")
            error_output = io.StringIO()
            with (
                redirect_stderr(error_output),
                patch.dict("os.environ", {"RUNHAVEN_CACHE_HOME": directory}, clear=False),
                patch("runhaven.cli.require_container_cli"),
                patch("runhaven.cli.run_preflight"),
                patch("runhaven.cli.inspect_internal_network", return_value=network_info),
                patch("runhaven.cli.create_provider_proxy", return_value=fake_proxy),
                patch("runhaven.cli.threading.Thread", return_value=thread),
                patch("runhaven.cli.delete_container_network"),
                patch("runhaven.cli.subprocess.call", return_value=0),
            ):
                code = main(
                    [
                        "run",
                        "shell",
                        "--workspace",
                        directory,
                        "--network",
                        "provider",
                        "--provider-host",
                        "example.com",
                        "--tty",
                        "never",
                        "--",
                        "/bin/true",
                    ]
                )

            self.assertEqual(code, 0)
            entries = [
                json.loads(line)
                for line in (Path(directory) / "egress-policy.jsonl").read_text().splitlines()
            ]
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["run_id"], entries[1]["run_id"])
            self.assertEqual(len(entries[0]["run_id"]), 32)
            self.assertEqual(entries[0]["decision"], "allowed")
            self.assertEqual(entries[0]["host"], "api.example.com")
            self.assertEqual(entries[0]["count"], 2)
            self.assertEqual(entries[1]["decision"], "denied")
            self.assertEqual(entries[1]["reason"], "not-in-allowlist")


if __name__ == "__main__":
    unittest.main()
