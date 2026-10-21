"""Exercise the real uploader with GITHUB_TOKEN and remove only this run's fixture."""

import argparse
import json
from pathlib import Path
import subprocess

from github_release_upload import GitHub, require, sha, stage_release, verify_release
from github_release_upload import wait_for_created_draft


def api(endpoint, *, method="GET", fields=(), missing_ok=False):
    command = ["gh", "api", "--method", method, endpoint]
    for name, value in fields:
        command.extend(["-f", f"{name}={value}"])
    result = subprocess.run(command, text=True, capture_output=True, timeout=120)
    if result.returncode:
        if missing_ok:
            try:
                if str(json.loads(result.stdout).get("status")) == "404":
                    return None
            except (ValueError, AttributeError):
                pass
        raise RuntimeError(f"{method} {endpoint}: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


class SmokeGitHub(GitHub):
    def __init__(self, repository, tag):
        super().__init__(repository, tag)
        self.creates = 0
        self.downloads = []

    def create(self, version, commit):
        self.creates += 1
        super().create(version, commit)

    def download(self, asset, destination):
        super().download(asset, destination)
        self.downloads.append({"name": asset["name"], "sha256": sha(destination)})


def clean_fixture(backend, version, commit, expected_names):
    """Never delete a public release, another draft, or a moved tag."""
    diagnostics = []
    record = wait_for_created_draft(backend, diagnostics) if backend.creates else backend.load()
    prefix = f"repos/{backend.repository}"
    ref_endpoint = f"{prefix}/git/ref/tags/{backend.tag}"
    ref = api(ref_endpoint)
    require(ref["object"]["sha"] == commit, "Fixture tag moved; preserving it")
    release_id = None
    if record is not None:
        require(record.get("draft") is True, "Fixture is public; preserving it")
        require(record.get("tag_name") == backend.tag, "Foreign fixture tag")
        require(
            record.get("body", "").startswith(f"Version {version}; verified source {commit}. "),
            "Foreign fixture notes; preserving draft",
        )
        require(
            {asset["name"] for asset in record["assets"]} <= expected_names,
            "Foreign fixture assets; preserving draft",
        )
        release_id = record["id"]
        api(f"{prefix}/releases/{release_id}", method="DELETE")
        require(
            api(f"{prefix}/releases/{release_id}", missing_ok=True) is None,
            "Fixture release still exists",
        )
    api(f"{prefix}/git/refs/tags/{backend.tag}", method="DELETE")
    require(api(ref_endpoint, missing_ok=True) is None, "Fixture tag still exists")
    return {"release_id": release_id, "tag": backend.tag, "verified_absent": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    require(args.run_id > 0 and 0 < args.attempt < 10000, "Invalid workflow identity")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    require(head == args.commit, "Fixture must use the checked-out commit")
    version = f"0.0.0rc{args.run_id * 10000 + args.attempt}"
    tag = "v" + version
    backend = SmokeGitHub(args.repository, tag)
    output = args.directory
    output.mkdir(parents=True, exist_ok=False)
    files = output / "assets"
    files.mkdir()
    (files / "uploader-smoke.txt").write_text(
        f"Temporary uploader test only; {args.repository}; {args.run_id}; {args.commit}\n"
    )
    manifest = {
        "version": version,
        "commit": args.commit,
        "files": {"uploader-smoke.txt": sha(files / "uploader-smoke.txt")},
    }
    (files / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    sums = "".join(f"{sha(path)}  {path.name}\n" for path in sorted(files.iterdir()))
    (files / "SHA256SUMS").write_text(sums)
    expected = {path.name: sha(path) for path in files.iterdir()}
    result = {
        "repository": args.repository,
        "commit": args.commit,
        "run_id": args.run_id,
        "attempt": args.attempt,
        "tag": tag,
        "fixture_only": True,
        "sha256": expected,
        "draft_visibility": [],
        "status": "failed",
    }
    tag_created = False
    try:
        require(backend.load() is None, "Fixture release already exists; preserving it")
        api(
            f"repos/{args.repository}/git/refs",
            method="POST",
            fields=(("ref", "refs/tags/" + tag), ("sha", args.commit)),
        )
        tag_created = True
        result["stage"] = stage_release(
            files,
            version,
            args.commit,
            tag,
            backend,
            visibility_diagnostics=result["draft_visibility"],
        )
        result["verify"] = verify_release(files, version, args.commit, tag, backend)
        require(backend.creates == 1, "Fixture must exercise exactly one fresh create")
        require(result["verify"]["status"] == "verified-draft", "Fixture must remain private")
        require(
            {item["name"]: item["sha256"] for item in backend.downloads} == expected,
            "Downloaded fixture hashes differ",
        )
        result["status"] = "passed"
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    finally:
        result["creates"] = backend.creates
        result["downloads"] = backend.downloads
        if tag_created:
            try:
                result["cleanup"] = clean_fixture(backend, version, args.commit, set(expected))
            except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
                result["status"] = "failed"
                result["cleanup_error"] = str(error)
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
