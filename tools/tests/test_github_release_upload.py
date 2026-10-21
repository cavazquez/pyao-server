"""Partial responses must never overwrite approved release bytes."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from subprocess import CompletedProcess

spec = importlib.util.spec_from_file_location(
    "github_release_upload", Path(__file__).parents[1] / "github_release_upload.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class GitHubLookupTests(unittest.TestCase):
    def backend(self):
        return release.GitHub("owner/project", "v1.0.0rc4")

    def missing(self):
        return CompletedProcess([], 1, json.dumps({"status": "404"}), "not found")

    def test_finds_draft_by_exact_tag_in_later_listing_page(self):
        draft = {"tag_name": "v1.0.0rc4", "draft": True, "assets": []}
        pages = [[{"tag_name": "v1.0.0rc40"}], [draft]]
        with patch.object(
            release.subprocess,
            "run",
            side_effect=[self.missing(), CompletedProcess([], 0, json.dumps(pages), "")],
        ) as run:
            self.assertEqual(self.backend().load(), draft)
        self.assertIn("--paginate", run.call_args.args[0])
        self.assertIn("--slurp", run.call_args.args[0])

    def test_returns_none_only_after_successful_listing_without_the_tag(self):
        with patch.object(
            release.subprocess,
            "run",
            side_effect=[self.missing(), CompletedProcess([], 0, "[[]]", "")],
        ):
            self.assertIsNone(self.backend().load())

    def test_preserves_permission_error_without_trying_a_listing(self):
        with patch.object(
            release.subprocess,
            "run",
            return_value=CompletedProcess([], 1, '{"status": "403"}', "forbidden"),
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "Cannot inspect release"):
                self.backend().load()
        self.assertEqual(run.call_count, 1)

    def test_does_not_treat_failed_listing_as_a_missing_release(self):
        with patch.object(
            release.subprocess,
            "run",
            side_effect=[self.missing(), CompletedProcess([], 1, "", "network failure")],
        ):
            with self.assertRaisesRegex(RuntimeError, "Cannot inspect release drafts"):
                self.backend().load()

    def test_refuses_duplicate_or_malformed_listings(self):
        for pages in (
            [[{"tag_name": "v1.0.0rc4"}, {"tag_name": "v1.0.0rc4"}]],
            {"items": []},
            [[None]],
        ):
            with (
                self.subTest(pages=pages),
                patch.object(
                    release.subprocess,
                    "run",
                    side_effect=[self.missing(), CompletedProcess([], 0, json.dumps(pages), "")],
                ),
            ):
                with self.assertRaises(ValueError):
                    self.backend().load()


class MemoryGitHub:
    def __init__(self):
        self.exists = False
        self.draft = True
        self.data = {}
        self.uploads = []
        self.creates = 0
        self.publications = 0
        self.lost_create = False
        self.lost_upload = False

    def load(self):
        if not self.exists:
            return None
        return {
            "tag_name": "v1.0.0rc4",
            "draft": self.draft,
            "prerelease": True,
            "assets": [
                {"name": name, "state": "uploaded", "size": len(data)}
                for name, data in self.data.items()
            ],
        }

    def create(self, _version, _commit):
        self.exists = True
        self.creates += 1
        if self.lost_create:
            raise RuntimeError("Response lost after draft creation")

    def upload(self, path):
        if path.name in self.data:
            raise RuntimeError("Already exists")
        self.uploads.append(path.name)
        self.data[path.name] = path.read_bytes()
        if self.lost_upload:
            self.lost_upload = False
            raise RuntimeError("Response lost after asset upload")

    def download(self, asset, target):
        target.write_bytes(self.data[asset["name"]])

    def publish(self, _prerelease):
        self.publications += 1
        self.draft = False


class ReleaseUploadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.version, self.commit, self.tag = "1.0.0rc4", "a" * 40, "v1.0.0rc4"
        (self.folder / "client.zip").write_bytes(b"candidate")
        (self.folder / "client.json").write_bytes(b"{}")
        files = {name: release.sha(self.folder / name) for name in ("client.zip", "client.json")}
        (self.folder / "release-manifest.json").write_text(
            json.dumps(
                {
                    "version": self.version,
                    "commit": self.commit,
                    "files": files,
                }
            )
        )
        sums = "".join(
            f"{release.sha(path)}  {path.name}\n" for path in sorted(self.folder.iterdir())
        )
        (self.folder / "SHA256SUMS").write_text(sums)
        self.backend = MemoryGitHub()

    def stage(self, **kwargs):
        return release.stage_release(
            self.folder, self.version, self.commit, self.tag, self.backend, **kwargs
        )

    def fill_remote(self):
        self.backend.exists = True
        self.backend.data = {p.name: p.read_bytes() for p in self.folder.iterdir()}

    def test_new_draft_is_uploaded_once_and_fully_verified(self):
        result = self.stage()
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "verified-draft")
        self.assertEqual(set(self.backend.uploads), {p.name for p in self.folder.iterdir()})
        self.assertEqual(self.backend.creates, 1)
        self.assertEqual(self.backend.publications, 0)

    def test_partial_draft_only_uploads_missing_assets(self):
        self.backend.exists = True
        self.backend.data["client.zip"] = b"candidate"
        self.stage()
        self.assertNotIn("client.zip", self.backend.uploads)
        self.assertEqual(self.backend.data["client.zip"], b"candidate")
        self.assertEqual(self.backend.creates, 0)

    def test_same_size_but_different_hash_aborts_before_any_upload(self):
        self.backend.exists = True
        self.backend.data["client.zip"] = b"tampered!"
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.stage()
        self.assertEqual(self.backend.uploads, [])
        self.assertEqual(self.backend.data["client.zip"], b"tampered!")

    def test_published_release_is_verified_without_mutation(self):
        self.fill_remote()
        self.backend.draft = False
        result = self.stage()
        self.assertEqual(result["status"], "verified-published")
        self.assertEqual(
            (self.backend.creates, self.backend.uploads, self.backend.publications),
            (0, [], 0),
        )

    def test_published_release_cannot_be_completed_by_uploading(self):
        self.backend.exists = True
        self.backend.draft = False
        with self.assertRaisesRegex(ValueError, "missing"):
            self.stage()
        self.assertEqual(self.backend.uploads, [])

    def test_lost_create_response_is_recovered_without_another_create(self):
        self.backend.lost_create = True
        self.assertTrue(self.stage()["verified"])
        self.assertEqual(self.backend.creates, 1)

    def test_lost_upload_response_is_recovered_without_duplicate_upload(self):
        self.backend.lost_upload = True
        self.assertTrue(self.stage()["verified"])
        self.assertEqual(len(self.backend.uploads), len(set(self.backend.uploads)))

    def test_local_corruption_is_rejected_before_creation(self):
        (self.folder / "client.zip").write_bytes(b"tampered!")
        with self.assertRaisesRegex(ValueError, "Local asset changed"):
            self.stage()
        self.assertFalse(self.backend.exists)

    def test_unknown_remote_asset_is_preserved_and_blocks_changes(self):
        self.backend.exists = True
        self.backend.data["foreign.txt"] = b"preserve"
        with self.assertRaisesRegex(ValueError, "Unexpected remote"):
            self.stage()
        self.assertEqual(self.backend.data, {"foreign.txt": b"preserve"})

    def test_dry_run_does_not_create_upload_or_publish(self):
        result = self.stage(dry_run=True)
        self.assertEqual(result["status"], "planned")
        self.assertFalse(result["verified"])
        self.assertFalse(self.backend.exists)
        self.assertEqual(self.backend.uploads, [])

    def test_publication_requires_all_bytes_and_is_idempotent(self):
        self.stage()
        for _ in range(2):
            result = release.verify_release(
                self.folder,
                self.version,
                self.commit,
                self.tag,
                self.backend,
                publish=True,
            )
            self.assertEqual(result["status"], "verified-published")
        self.assertEqual(self.backend.publications, 1)


if __name__ == "__main__":
    unittest.main()
