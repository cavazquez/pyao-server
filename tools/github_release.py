"""Prepare GitHub assets from successful CI artifacts; never compile or overwrite releases."""

import argparse
import base64
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
import zipfile


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def version(text, role):
    if role == "server":
        return tomllib.loads(text)["project"]["version"]
    match = re.search(r'^config/version="([^"]+)"$', text, re.MULTILINE)
    if match is None:
        raise ValueError("Missing product version")
    return match[1]


def check_run(record, jobs, commit, workflow, required):
    if not (
        record["head_sha"] == commit
        and record["path"] == ".github/workflows/" + workflow
        and record["event"] == "workflow_dispatch"
        and record["status"] == "completed"
        and record["conclusion"] == "success"
        and record["head_repository"]["full_name"] == record["repository"]["full_name"]
    ):
        raise ValueError("CI run has another source, workflow, event or result")
    successful = {job["name"] for job in jobs["jobs"] if job["conclusion"] == "success"}
    missing = [pattern for pattern in required if not any(fnmatch.fnmatchcase(name, pattern) for name in successful)]
    if missing:
        raise ValueError("Missing successful required jobs: " + str(missing))


def preflight(tag, role):
    if re.fullmatch(r"v\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", tag) is None:
        raise ValueError("Expected a product tag such as v1.0.0rc3")
    commit = command("git", "rev-parse", tag + "^{commit}")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"], check=True)
    filename = "pyproject.toml" if role == "server" else "project.godot"
    product = version(command("git", "show", commit + ":" + filename), role)
    if tag != "v" + product:
        raise ValueError("Tag and source version differ")
    peer_role = "client" if role == "server" else "server"
    peer_repo = "ArgentumOnlineGodot" if role == "server" else "pyao-server"
    peer_file = "project.godot" if role == "server" else "pyproject.toml"
    peer = json.loads(command("gh", "api", f"repos/cavazquez/{peer_repo}/contents/{peer_file}?ref={tag}"))
    if version(base64.b64decode(peer["content"]).decode(), peer_role) != product:
        raise ValueError("Client and server versions differ")
    result = {"commit": commit, "version": product, "prerelease": str(bool(re.search(r"[ab]|rc", product))).lower()}
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
        for key, value in result.items():
            stream.write(f"{key}={value}\n")
    with Path(os.environ["GITHUB_ENV"]).open("a") as stream:
        for key, value in result.items():
            stream.write(f"RELEASE_{key.upper()}={value}\n")


def identity(record, product, commit):
    if record.get("version") != product or record.get("commit") != commit or record.get("dirty") is not False:
        raise ValueError("Artifact provenance differs from the clean tagged source")


def snapshot(directory):
    product = version(Path("project.godot").read_text(), "client")
    record = {"version": product, "commit": command("git", "rev-parse", "HEAD"),
              "dirty": bool(command("git", "status", "--porcelain")),
              "files": {"pyao-client.x86_64": sha(directory / "pyao-client.x86_64")}}
    if record["dirty"]:
        raise ValueError("Native export must come from a clean source")
    (directory / "release-manifest.json").write_text(json.dumps(record, indent=2) + "\n")


def prepare(incoming, output, product, commit, role):
    if output.exists():
        raise ValueError("Output already exists; assets are immutable")
    if role == "client":
        native = incoming / "native"
        record = json.loads((native / "release-manifest.json").read_text())
        identity(record, product, commit)
        executable = native / "pyao-client.x86_64"
        if record["files"] != {executable.name: sha(executable)}:
            raise ValueError("Native executable changed after CI")
        arches = ["amd64"]
    else:
        native = incoming / "distribution"
        record = json.loads((native / "manifest.json").read_text())
        if record["version"] != product or not record["verified_install"]:
            raise ValueError("Distribution was not validated for this version")
        arches = ["amd64", "arm64"]
    snaps = []
    for arch in arches:
        folder = incoming / arch
        proof = json.loads((folder / "snap/pyao-source.json").read_text())
        identity(proof, product, commit)
        actual_arch = proof["architecture"] if role == "server" else proof["toolchain"]["architecture"]
        if actual_arch != arch:
            raise ValueError("Wrong Snap architecture")
        name = "pyao" if role == "server" else "pyao-client"
        snap = folder / f"{name}_{product}_{arch}.snap"
        sums = folder / ("artifacts/SHA256SUMS" if role == "server" else "build/snap-sha256.txt")
        if sums.read_text().split() != [sha(snap), snap.name]:
            raise ValueError("Snap changed after CI")
        snaps.append(snap)
    output.mkdir(parents=True)
    if role == "client":
        executable.chmod(0o755)
        with zipfile.ZipFile(output / f"pyao-client-{product}-linux-amd64.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(executable, executable.name)
            archive.write(native / "release-manifest.json", "release-manifest.json")
    else:
        for item in record["files"]:
            name = item["name"]
            if Path(name).name != name or sha(native / name) != item["sha256"]:
                raise ValueError("Invalid distribution hash or filename")
            if name not in (f"pyao_server-{product}-py3-none-any.whl", f"pyao_server-{product}.tar.gz"):
                raise ValueError("Unexpected distribution filename")
            shutil.copyfile(native / name, output / name)
        if len(record["files"]) != 2 or len(list(output.iterdir())) != 2:
            raise ValueError("A wheel and sdist are required")
    for snap in snaps:
        shutil.copyfile(snap, output / snap.name)
    proof = {"version": product, "commit": commit,
             "files": {p.name: sha(p) for p in sorted(output.iterdir())}}
    (output / "release-manifest.json").write_text(json.dumps(proof, indent=2) + "\n")
    (output / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.name}\n" for p in sorted(output.iterdir())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["preflight", "check-run", "snapshot", "prepare"])
    parser.add_argument("--role", choices=["server", "client"], default="client")
    parser.add_argument("--tag")
    parser.add_argument("--commit")
    parser.add_argument("--version")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--jobs", type=Path)
    parser.add_argument("--workflow")
    parser.add_argument("--required", action="append", default=[])
    parser.add_argument("--directory", type=Path, default=Path("build"))
    parser.add_argument("--output", type=Path, default=Path("release-dist"))
    args = parser.parse_args()
    if args.operation == "preflight":
        preflight(args.tag, args.role)
    elif args.operation == "check-run":
        check_run(json.loads(args.run.read_text()), json.loads(args.jobs.read_text()), args.commit, args.workflow, args.required)
    elif args.operation == "snapshot":
        snapshot(args.directory)
    else:
        prepare(args.directory, args.output, args.version, args.commit, args.role)
