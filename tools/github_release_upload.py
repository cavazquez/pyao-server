"""Stage, verify and publish immutable GitHub assets, resuming partial drafts."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


DRAFT_VISIBILITY_TIMEOUT = 60


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def payloads(directory, version, commit):
    """Validate every local byte before making a remote change."""
    require(re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", version), "Invalid version")
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "Invalid commit")
    manifest = json.loads((directory / "release-manifest.json").read_text())
    require(
        manifest.get("version") == version and manifest.get("commit") == commit,
        "Manifest identifies another source",
    )
    files = manifest["files"]
    require(isinstance(files, dict) and files, "Empty release manifest")
    names = set(files) | {"release-manifest.json", "SHA256SUMS"}
    require(set(p.name for p in directory.iterdir()) == names, "Unexpected local assets")
    for name in names:
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name), "Unsafe asset name")
        path = directory / name
        require(path.is_file() and not path.is_symlink(), "Asset must be a regular file")
    checksums = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(
            name not in checksums and re.fullmatch(r"[0-9a-f]{64}", digest),
            "Invalid or duplicate checksum",
        )
        checksums[name] = digest
    require(set(checksums) == names - {"SHA256SUMS"}, "Incomplete checksum manifest")
    for name, digest in checksums.items():
        require(sha(directory / name) == digest, "Local asset changed: " + name)
    for name, digest in files.items():
        require(
            name in checksums and checksums[name] == digest,
            "Manifest checksum differs: " + name,
        )
    return {name: directory / name for name in sorted(names)}


class GitHub:
    def __init__(self, repository, tag):
        require(re.fullmatch(r"[\w.-]+/[\w.-]+", repository), "Invalid repository")
        self.repository, self.tag = repository, tag

    def load(self, *, timeout=120):
        deadline = time.monotonic() + timeout
        result = subprocess.run(
            ["gh", "api", f"repos/{self.repository}/releases/tags/{self.tag}"],
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode:
            try:
                missing = str(json.loads(result.stdout).get("status")) == "404"
            except (ValueError, AttributeError):
                missing = False
            if missing:
                # The tag endpoint only returns published releases. Authenticated
                # listings also include drafts; never mistake a partial draft for
                # a missing release and attempt to create it again.
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired("Inspect release drafts", timeout)
                return self.find_draft(timeout=remaining)
            raise RuntimeError("Cannot inspect release: " + result.stderr.strip())
        return json.loads(result.stdout)

    def find_draft(self, *, timeout=120):
        result = subprocess.run(
            [
                "gh",
                "api",
                "--paginate",
                "--slurp",
                f"repos/{self.repository}/releases?per_page=100",
            ],
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode:
            raise RuntimeError("Cannot inspect release drafts: " + result.stderr.strip())
        pages = json.loads(result.stdout)
        require(
            isinstance(pages, list) and all(isinstance(page, list) for page in pages),
            "Invalid paginated release listing",
        )
        records = [record for page in pages for record in page]
        require(all(isinstance(record, dict) for record in records), "Invalid release records")
        matches = [record for record in records if record.get("tag_name") == self.tag]
        require(len(matches) <= 1, "Duplicate releases for the same tag")
        return matches[0] if matches else None

    def create(self, version, commit):
        args = [
            "gh",
            "release",
            "create",
            self.tag,
            "--repo",
            self.repository,
            "--verify-tag",
            "--draft",
            "--latest=false",
            "--title",
            self.repository.split("/")[1] + " " + version,
            "--notes",
            f"Version {version}; verified source {commit}. "
            "SHA256SUMS and release-manifest.json identify the approved assets.",
        ]
        if re.search(r"[ab]|rc", version):
            args.append("--prerelease")
        # Uploading is deliberately separate: bulk create/upload can leave a
        # partial draft after a 408/422 response.
        subprocess.run(args, check=True, timeout=120)

    def upload(self, path):
        subprocess.run(
            ["gh", "release", "upload", self.tag, str(path), "--repo", self.repository],
            check=True,
            timeout=1800,
        )

    def download(self, asset, destination):
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                self.tag,
                "--repo",
                self.repository,
                "--pattern",
                asset["name"],
                "--dir",
                str(destination.parent),
            ],
            check=True,
            timeout=1800,
        )

    def publish(self, prerelease):
        subprocess.run(
            [
                "gh",
                "release",
                "edit",
                self.tag,
                "--repo",
                self.repository,
                "--draft=false",
                "--prerelease=" + str(prerelease).lower(),
                "--latest=" + str(not prerelease).lower(),
            ],
            check=True,
            timeout=120,
        )


def inspect_release(record, files, version, tag, backend, *, complete):
    require(
        record is not None and record.get("tag_name") == tag,
        "Release missing or wrong tag",
    )
    require(isinstance(record.get("draft"), bool), "Invalid release draft flag")
    require(
        record.get("prerelease") is bool(re.search(r"[ab]|rc", version)),
        "Release has an incompatible prerelease flag",
    )
    assets = record["assets"]
    names = [asset["name"] for asset in assets]
    require(len(set(names)) == len(names), "Duplicate remote asset names")
    require(set(names) <= set(files), "Unexpected remote assets; refusing to modify release")
    if complete:
        require(set(names) == set(files), "Release is missing approved assets")
    with tempfile.TemporaryDirectory(prefix="pyao-release-verify-") as temp:
        for asset in assets:
            name = asset["name"]
            local = files[name]
            require(
                asset.get("state") == "uploaded" and asset["size"] == local.stat().st_size,
                "Incomplete or different remote asset: " + name,
            )
            downloaded = Path(temp) / name
            backend.download(asset, downloaded)
            require(sha(downloaded) == sha(local), "Remote checksum differs: " + name)
    return set(names)


def wait_for_created_draft(backend, diagnostics, *, timeout=DRAFT_VISIBILITY_TIMEOUT):
    """Poll absence after one create; all lookup errors remain fatal."""
    require(0 < timeout <= 600, "Draft visibility timeout must be between 0 and 600 seconds")
    started = time.monotonic()
    deadline = started + timeout
    attempt = 0
    pause = 1
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"Created draft remained invisible for {timeout:g} seconds; "
                "creation was not repeated"
            )
        attempt += 1
        event = {"attempt": attempt}
        try:
            record = backend.load(timeout=remaining)
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
            event.update(status="failed", error=str(error))
            raise
        else:
            event["status"] = "missing" if record is None else "visible"
        finally:
            event["elapsed_seconds"] = round(time.monotonic() - started, 3)
            diagnostics.append(event)
            print(json.dumps({"draft_visibility": event}), file=sys.stderr, flush=True)
        if record is not None:
            return record
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(pause, remaining))
            pause = min(pause * 2, 5)


def stage_release(
    directory,
    version,
    commit,
    tag,
    backend,
    *,
    dry_run=False,
    visibility_diagnostics=None,
    visibility_timeout=DRAFT_VISIBILITY_TIMEOUT,
):
    require(tag == "v" + version, "Tag and version differ")
    files = payloads(directory, version, commit)
    record = backend.load()
    if record is not None:
        existing = inspect_release(
            record, files, version, tag, backend, complete=not record["draft"]
        )
        if not record["draft"]:
            return {"status": "verified-published", "verified": True, "uploaded": []}
    else:
        existing = set()
    missing = sorted(set(files) - existing)
    if dry_run:
        return {"status": "planned", "verified": False, "missing": missing}
    if record is None:
        creation_error = None
        try:
            backend.create(version, commit)
        except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            # A response can be lost after GitHub created the draft. Inspect the
            # concrete result; never blindly issue another create.
            creation_error = error
        diagnostics = visibility_diagnostics if visibility_diagnostics is not None else []
        try:
            record = wait_for_created_draft(backend, diagnostics, timeout=visibility_timeout)
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
            if creation_error is not None:
                raise RuntimeError(
                    f"Draft creation response failed: {creation_error}; "
                    f"visibility check failed: {error}"
                ) from creation_error
            raise
        existing = inspect_release(record, files, version, tag, backend, complete=False)
        require(record["draft"], "Creation did not leave a draft")
        missing = sorted(set(files) - existing)
    uploaded = []
    for name in missing:
        try:
            backend.upload(files[name])
        except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Recover a lost upload response only when the named bytes can be
            # downloaded and verified. Never use --clobber or delete an asset.
            record = backend.load()
            existing = inspect_release(record, files, version, tag, backend, complete=False)
            require(record["draft"] and name in existing, "Upload incomplete: " + name)
        uploaded.append(name)
    record = backend.load()
    inspect_release(record, files, version, tag, backend, complete=True)
    return {
        "status": "verified-draft" if record["draft"] else "verified-published",
        "verified": True,
        "uploaded": uploaded,
    }


def verify_release(directory, version, commit, tag, backend, *, publish=False, dry_run=False):
    require(tag == "v" + version, "Tag and version differ")
    files = payloads(directory, version, commit)
    record = backend.load()
    inspect_release(record, files, version, tag, backend, complete=True)
    if publish and record["draft"] and not dry_run:
        try:
            backend.publish(bool(record["prerelease"]))
        except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            record = backend.load()
            inspect_release(record, files, version, tag, backend, complete=True)
            require(not record["draft"], "Publication remains incomplete")
        record = backend.load()
        require(not record["draft"], "Publication did not change draft state")
    return {
        "status": "verified-draft" if record["draft"] else "verified-published",
        "verified": True,
        "publication_planned": bool(publish and dry_run),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("stage", "verify", "publish"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    backend = GitHub(args.repository, args.tag)
    failed = False
    visibility = []
    try:
        if args.operation == "stage":
            result = stage_release(
                args.directory,
                args.version,
                args.commit,
                args.tag,
                backend,
                dry_run=args.dry_run,
                visibility_diagnostics=visibility,
            )
        else:
            result = verify_release(
                args.directory,
                args.version,
                args.commit,
                args.tag,
                backend,
                publish=args.operation == "publish",
                dry_run=args.dry_run,
            )
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        result = {"status": "failed", "verified": False, "error": str(error)}
        failed = True
    result.update(
        repository=args.repository,
        tag=args.tag,
        version=args.version,
        commit=args.commit,
        draft_visibility=visibility,
    )
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if failed:
        raise SystemExit(1)
