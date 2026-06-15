from __future__ import annotations

import unittest

from runhaven.images import (
    RUNHAVEN_PROFILE_LABEL,
    RUNHAVEN_SOURCE_DIGEST_LABEL,
    build_image_plan,
)
from runhaven.profiles import get_profile


class ImagePlanTests(unittest.TestCase):
    def test_custom_tag_is_used_for_build(self) -> None:
        plan = build_image_plan(get_profile("shell"), tag="runhaven/test:0.1.0")

        self.assertEqual(plan.command[3], "runhaven/test:0.1.0")

    def test_build_labels_include_profile_and_source_digest(self) -> None:
        plan = build_image_plan(get_profile("shell"))

        labels = [
            plan.command[index + 1]
            for index, value in enumerate(plan.command)
            if value == "--label"
        ]
        self.assertIn(f"{RUNHAVEN_PROFILE_LABEL}=shell", labels)
        digest_labels = [
            label for label in labels if label.startswith(f"{RUNHAVEN_SOURCE_DIGEST_LABEL}=")
        ]
        self.assertEqual(len(digest_labels), 1)
        self.assertRegex(
            digest_labels[0].removeprefix(f"{RUNHAVEN_SOURCE_DIGEST_LABEL}="),
            r"^[a-f0-9]{64}$",
        )

    def test_rejects_unsafe_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "image tag"):
            build_image_plan(get_profile("shell"), tag="--debug")


if __name__ == "__main__":
    unittest.main()
