from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from runhaven.cli import ensure_internal_network


class CliProviderInternalNetworkTests(unittest.TestCase):
    def test_existing_internal_network_is_reused(self) -> None:
        with patch("runhaven.cli.subprocess.run") as run:
            run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([{"configuration": {"mode": "hostOnly"}}]),
                stderr="",
            )

            ensure_internal_network("runhaven-project-internal")

        run.assert_called_once()
        self.assertEqual(
            run.call_args.args[0],
            ("container", "network", "inspect", "runhaven-project-internal"),
        )

    def test_existing_non_internal_network_is_rejected(self) -> None:
        with patch("runhaven.cli.subprocess.run") as run:
            run.return_value = Mock(
                returncode=0,
                stdout=json.dumps([{"configuration": {"mode": "nat"}}]),
                stderr="",
            )

            with self.assertRaisesRegex(ValueError, "not host-only"):
                ensure_internal_network("runhaven-project-internal")

    def test_missing_internal_network_is_created(self) -> None:
        with patch("runhaven.cli.subprocess.run") as run:
            run.side_effect = [Mock(returncode=1, stdout="", stderr=""), Mock(returncode=0)]

            ensure_internal_network("runhaven-project-internal")

        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[1].args[0],
            ("container", "network", "create", "--internal", "runhaven-project-internal"),
        )


if __name__ == "__main__":
    unittest.main()
