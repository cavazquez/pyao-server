"""Release provenance must fail closed without building any game executable."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("github_release", Path(__file__).parents[1] / "github_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.commit = "a" * 40
        self.run = {"head_sha": self.commit, "path": ".github/workflows/client-linux.yml",
                    "event": "workflow_dispatch", "status": "completed", "conclusion": "success",
                    "head_repository": {"full_name": "owner/repo"}, "repository": {"full_name": "owner/repo"}}
        self.jobs = {"jobs": [{"name": "package-snap", "conclusion": "success"}]}

    def test_successful_manual_run(self):
        release.check_run(self.run, self.jobs, self.commit, "client-linux.yml", ["package-snap"])

    def test_wrong_source_event_workflow_and_result_are_rejected(self):
        for key, value in [("head_sha", "b" * 40), ("event", "pull_request"),
                           ("path", ".github/workflows/other.yml"), ("conclusion", "failure"),
                           ("status", "in_progress"), ("head_repository", {"full_name": "fork/repo"})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                record = copy.deepcopy(self.run)
                record[key] = value
                release.check_run(record, self.jobs, self.commit, "client-linux.yml", ["package-snap"])

    def test_skipped_packaging_does_not_qualify_as_a_release(self):
        self.jobs["jobs"][0]["conclusion"] = "skipped"
        with self.assertRaises(ValueError):
            release.check_run(self.run, self.jobs, self.commit, "client-linux.yml", ["package-snap"])

    def test_provenance_requires_same_version_commit_and_clean_source(self):
        record = {"version": "1.0.0rc3", "commit": self.commit, "dirty": False}
        release.identity(record, "1.0.0rc3", self.commit)
        for key, value in [("version", "1.0.0rc2"), ("commit", "b" * 40), ("dirty", True), ("dirty", None)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.identity(dict(record, **{key: value}), "1.0.0rc3", self.commit)

    def test_changed_native_artifact_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as temp:
            incoming = Path(temp) / "incoming"
            native = incoming / "native"
            native.mkdir(parents=True)
            (native / "pyao-client.x86_64").write_text("synthetic test fixture")
            (native / "release-manifest.json").write_text(json.dumps({
                "version": "1.0.0rc3", "commit": self.commit, "dirty": False,
                "files": {"pyao-client.x86_64": "0" * 64},
            }))
            output = Path(temp) / "out"
            with self.assertRaisesRegex(ValueError, "changed"):
                release.prepare(incoming, output, "1.0.0rc3", self.commit, "client")
            self.assertFalse(output.exists())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, "exists"):
            release.prepare(Path("unused"), Path(temp), "1.0.0rc3", self.commit, "client")
