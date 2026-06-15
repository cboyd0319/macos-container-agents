from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

from runhaven.cli import main
from runhaven.images import RUNHAVEN_SOURCE_DIGEST_LABEL


class CliImageTests(unittest.TestCase):
    def test_image_doctor_reports_missing_bundled_image(self) -> None:
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch("runhaven.cli.require_container_cli"),
            patch("runhaven.cli.subprocess.run") as run,
        ):
            run.side_effect = [
                Mock(
                    returncode=0,
                    stdout='[{"configuration": {"name": "runhaven/base:0.1.0"}}]',
                    stderr="",
                ),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            code = main(["image", "doctor", "claude"])

        self.assertEqual(code, 1)
        text = output.getvalue()
        self.assertIn("missing claude", text)
        self.assertIn("runhaven/claude:0.1.0", text)
        self.assertIn("runhaven image rebuild claude", text)
        self.assertIn("Preflight recovery", text)
        self.assertIn("runhaven network list", text)
        self.assertIn("runhaven network prune", text)
        self.assertIn("runhaven state reset claude --workspace PATH --yes", text)
        self.assertEqual(
            run.call_args_list,
            [
                call(
                    ("container", "image", "list", "--format", "json"),
                    check=False,
                    capture_output=True,
                    text=True,
                ),
                call(
                    ("container", "volume", "list", "--quiet"),
                    check=False,
                    capture_output=True,
                    text=True,
                ),
            ],
        )

    def test_image_doctor_reports_present_image(self) -> None:
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch("runhaven.cli.require_container_cli"),
            patch("runhaven.cli.subprocess.run") as run,
        ):
            run.side_effect = [
                Mock(
                    returncode=0,
                    stdout=(
                        '[{"configuration": {'
                        '"creationDate": "2999-01-01T00:00:00Z", '
                        '"name": "docker.io/runhaven/base:0.1.0"'
                        "}}]"
                    ),
                    stderr="",
                ),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            code = main(["image", "doctor", "shell"])

        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("ok shell", text)
        self.assertIn("runhaven/base:0.1.0", text)
        self.assertNotIn("missing shell", text)
        self.assertIn("No inactive RunHaven state volumes found", text)

    def test_image_doctor_reports_stale_image_when_template_is_newer(self) -> None:
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch("runhaven.cli.require_container_cli"),
            patch("runhaven.cli.subprocess.run") as run,
        ):
            run.side_effect = [
                Mock(
                    returncode=0,
                    stdout=(
                        '[{"configuration": {'
                        '"creationDate": "2000-01-01T00:00:00Z", '
                        '"name": "runhaven/base:0.1.0"'
                        "}}]"
                    ),
                    stderr="",
                ),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            code = main(["image", "doctor", "shell"])

        self.assertEqual(code, 1)
        text = output.getvalue()
        self.assertIn("stale shell", text)
        self.assertIn("template newer than local image", text)
        self.assertIn("runhaven image rebuild shell", text)

    def test_image_doctor_reports_stale_image_when_source_digest_differs(self) -> None:
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch("runhaven.cli.require_container_cli"),
            patch("runhaven.cli.subprocess.run") as run,
        ):
            run.side_effect = [
                Mock(
                    returncode=0,
                    stdout=json.dumps(
                        [
                            {
                                "configuration": {
                                    "creationDate": "2999-01-01T00:00:00Z",
                                    "name": "runhaven/base:0.1.0",
                                },
                                "variants": [
                                    {
                                        "config": {
                                            "config": {
                                                "Labels": {
                                                    RUNHAVEN_SOURCE_DIGEST_LABEL: "0" * 64,
                                                }
                                            }
                                        }
                                    }
                                ],
                            }
                        ]
                    ),
                    stderr="",
                ),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            code = main(["image", "doctor", "shell"])

        self.assertEqual(code, 1)
        text = output.getvalue()
        self.assertIn("stale shell", text)
        self.assertIn("bundled source digest differs", text)
        self.assertIn("runhaven image rebuild shell", text)

    def test_image_doctor_checks_all_profiles_by_default(self) -> None:
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch("runhaven.cli.require_container_cli"),
            patch("runhaven.cli.subprocess.run") as run,
        ):
            run.side_effect = [
                Mock(
                    returncode=0,
                    stdout=(
                        '[{"configuration": {'
                        '"creationDate": "2999-01-01T00:00:00Z", '
                        '"name": "runhaven/base:0.1.0"'
                        "}}]"
                    ),
                    stderr="",
                ),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            code = main(["image", "doctor"])

        self.assertEqual(code, 1)
        text = output.getvalue()
        self.assertIn("ok shell", text)
        self.assertIn("missing claude", text)
        self.assertIn("missing codex", text)
        self.assertIn("runhaven image rebuild claude", text)

    def test_image_doctor_reports_inactive_state_volumes_without_deleting(self) -> None:
        with TemporaryDirectory() as directory:
            active_dir = Path(directory) / "active-runs"
            active_dir.mkdir()
            (active_dir / "run-active.json").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-06-15T00:00:00Z",
                        "run_id": "run-active",
                        "container_name": "runhaven-shell-active-run",
                        "state_volume": "runhaven-shell-active-home",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                redirect_stdout(output),
                patch.dict("os.environ", {"RUNHAVEN_CACHE_HOME": directory}, clear=False),
                patch("runhaven.cli.require_container_cli"),
                patch("runhaven.cli.subprocess.run") as run,
            ):
                run.side_effect = [
                    Mock(
                        returncode=0,
                        stdout=(
                            '[{"configuration": {'
                            '"creationDate": "2999-01-01T00:00:00Z", '
                            '"name": "runhaven/base:0.1.0"'
                            "}}]"
                        ),
                        stderr="",
                    ),
                    Mock(
                        returncode=0,
                        stdout=(
                            "runhaven-shell-active-home\n"
                            "runhaven-shell-inactive-home\n"
                            "runhaven-claude-inactive-home\n"
                            "other-volume\n"
                        ),
                        stderr="",
                    ),
                ]

                code = main(["image", "doctor", "shell"])

        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("State volume review", text)
        self.assertIn("runhaven-shell-inactive-home", text)
        self.assertNotIn("runhaven-shell-active-home", text)
        self.assertNotIn("runhaven-claude-inactive-home", text)
        self.assertNotIn("other-volume", text)
        self.assertIn("runhaven state reset shell --workspace PATH --yes", text)
        self.assertFalse(
            any(
                call_args.args[0][:3] == ("container", "volume", "delete")
                for call_args in run.call_args_list
            )
        )

    def test_image_doctor_rejects_invalid_image_list_json(self) -> None:
        with (
            patch("runhaven.cli.require_container_cli"),
            patch("runhaven.cli.subprocess.run") as run,
        ):
            run.return_value = Mock(returncode=0, stdout="not json", stderr="")

            with self.assertRaises(SystemExit) as error:
                main(["image", "doctor", "shell"])

        self.assertEqual(error.exception.code, 2)
        run.assert_called_once_with(
            ("container", "image", "list", "--format", "json"),
            check=False,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
