"""Temporary release cleanup must preserve public or foreign resources."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with patch.dict(sys.modules, {"github_release_upload": load_module("github_release_upload")}):
    smoke = load_module("github_release_smoke")


class FixtureCleanupTests(unittest.TestCase):
    def setUp(self):
        self.version, self.commit = "0.0.0rc1230001", "a" * 40
        self.tag = "v" + self.version
        self.record = {
            "id": 123,
            "tag_name": self.tag,
            "draft": True,
            "body": f"Version {self.version}; verified source {self.commit}. Fixture only.",
            "assets": [{"name": "uploader-smoke.txt"}],
        }
        self.backend = SimpleNamespace(
            repository="owner/project", tag=self.tag, creates=0, load=Mock(return_value=self.record)
        )
        self.ref = {"object": {"sha": self.commit}}

    def clean(self):
        return smoke.clean_fixture(self.backend, self.version, self.commit, {"uploader-smoke.txt"})

    def test_owned_private_fixture_is_deleted_and_absence_is_verified(self):
        with patch.object(smoke, "api", side_effect=[self.ref, None, None, None, None]) as api:
            result = self.clean()
        self.assertTrue(result["verified_absent"])
        writes = [
            call.args[0] for call in api.call_args_list if call.kwargs.get("method") == "DELETE"
        ]
        self.assertEqual(
            writes,
            ["repos/owner/project/releases/123", "repos/owner/project/git/refs/tags/" + self.tag],
        )
        self.assertEqual(
            sum(call.kwargs.get("missing_ok", False) for call in api.call_args_list), 2
        )

    def test_moved_tag_is_preserved_without_any_delete(self):
        with patch.object(smoke, "api", return_value={"object": {"sha": "b" * 40}}) as api:
            with self.assertRaisesRegex(ValueError, "tag moved"):
                self.clean()
        self.assertEqual(api.call_count, 1)
        self.assertNotIn("method", api.call_args.kwargs)

    def test_public_or_foreign_draft_is_preserved_without_any_delete(self):
        for change in (
            {"draft": False},
            {"tag_name": "v1.0.0rc4"},
            {"body": "Someone else's release"},
            {"assets": [{"name": "production.snap"}]},
        ):
            with self.subTest(change=change):
                self.backend.load.return_value = self.record | change
                with patch.object(smoke, "api", return_value=self.ref) as api:
                    with self.assertRaises(ValueError):
                        self.clean()
                self.assertEqual(api.call_count, 1)
                self.assertNotIn("method", api.call_args.kwargs)

    def test_failed_lookup_never_starts_cleanup(self):
        self.backend.load.side_effect = RuntimeError("forbidden")
        with patch.object(smoke, "api") as api:
            with self.assertRaisesRegex(RuntimeError, "forbidden"):
                self.clean()
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
