"""Reuse the client graphical harness for scoped indexes and experimental runtimes.

No client source is changed. --build explicitly substitutes only the server
process with a hash-verified Nuitka candidate, including on restart. The source
fixture flag in the underlying runner describes the fixture, not that candidate.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from tools.analysis.nuitka_study import ROOT, source_hashes


def configure_scenario():
    import skills_world

    class ScopedWorld(skills_world.MechanicsWorld):
        def passed(self, key, requirement="", **observations):
            self.steps.append(
                {"id": key, "passed": True, "test_executed": True, "observations": observations}
            )
            self.save()
            print("SCOPED_WORLD: PASS", key, flush=True)

        def fire_visible(self, index, x, y, visible=True):
            def matches():
                probe = self.command(index, "loot_probe", x=x, y=y, graphic=1521)["loot_probe"]
                return all(probe.values()) if visible else not probe["visible"]

            return self.wait(
                matches,
                f"campfire visible={visible} client={index}",
            )

        def restart_both(self, store):
            for index in (1, 2):
                self.command(index, "logout")
                self.wait(
                    lambda index=index: not store.exists(f"session:{self.ids[index]}:owner"),
                    "release session",
                )
            self.server = self.restart_server()
            for index in (1, 2):
                self.command(index, "login")

        def run(self, locations):
            self.deadline = time.monotonic() + 600
            self.wait(
                lambda: all(
                    "INTEGRATION_WORLD: READY" in (self.output / f"godot-{i}.log").read_text()
                    for i in (1, 2)
                ),
                "two graphical clients",
                60,
            )
            with self.fixture.client() as store:
                self.ids = {
                    i: int(store.hget(f"account:{self.names[i - 1]}:data", "user_id"))
                    for i in (1, 2)
                }
                _, x, y = locations["skills_base"]
                self.base = {1: (2, x, y), 2: (2, x, y + 1)}
                self.reset(
                    store,
                    items={1: (58, 20)},
                    stats={"min_sta": 10, "max_sta": 100},
                    skills={"supervivencia": 90, "domar": 90},
                )
                self.attempt(store, 8, x - 1, y)
                fire = f"world:campfire:2:{x - 1}:{y}"
                self.wait(lambda: store.exists(fire), "persisted campfire")
                assert store.smembers("world:campfires:2") == {fire}
                until = float(store.hget(fire, "until"))
                for index in (1, 2):
                    self.command(index, "close_mechanics")
                    self.fire_visible(index, x - 1, y)
                    self.screen("campfire-visible", index)
                before = int(store.hget(f"player:{self.ids[1]}:user_stats", "min_sta"))
                self.command(1, "chat", text="/DESCANSAR")
                self.wait(
                    lambda: store.hget(f"player:{self.ids[1]}:user_stats", "resting") == "1",
                    "resting",
                )
                self.wait(
                    lambda: int(store.hget(f"player:{self.ids[1]}:user_stats", "min_sta")) > before,
                    "energy recovery",
                    10,
                )
                self.command(1, "chat", text="/DESCANSAR")
                self.passed(
                    "campfire-rest-energy",
                    energy_before=before,
                    energy_after=store.hget(f"player:{self.ids[1]}:user_stats", "min_sta"),
                )
                self.command(2, "logout")
                self.wait(
                    lambda: not store.exists(f"session:{self.ids[2]}:owner"), "reconnect release"
                )
                self.command(2, "login")
                self.fire_visible(2, x - 1, y)
                self.restart_both(store)
                for index in (1, 2):
                    self.fire_visible(index, x - 1, y)
                assert float(store.hget(fire, "until")) == until
                self.passed("campfire-reconnect-restart", until=until)
                for _ in range(35):
                    self.attempt(store, 17, x + 1, y)
                    if any(pet.get("is_tamed") == "True" for pet in self.pets(store)):
                        break
                pet = next(pet for pet in self.pets(store) if pet.get("is_tamed") == "True")
                identity, character = pet["instance_id"], pet["char_index"]
                assert identity in store.smembers(f"player:{self.ids[1]}:pets")
                for index in (1, 2):
                    self.command(index, "close_mechanics")
                    self.view(
                        index, lambda view: character in view["world_characters"], "pet visible"
                    )
                self.command(1, "chat", text="/QUIETO")
                self.wait(
                    lambda: store.hget(f"npc:instance:{identity}", "pet_order") == "wait",
                    "pet wait",
                )
                self.command(1, "chat", text="/ACOMPAÑAR")
                self.wait(
                    lambda: store.hget(f"npc:instance:{identity}", "pet_order") == "follow",
                    "pet follow",
                )
                self.restart_both(store)
                assert identity in store.smembers(f"player:{self.ids[1]}:pets")
                assert store.hget(f"npc:instance:{identity}", "is_tamed") == "True"
                for index in (1, 2):
                    self.view(
                        index,
                        lambda view: character in view["world_characters"],
                        "restored pet visible",
                    )
                self.command(2, "chat", text="/LIBERAR")
                assert store.exists(f"npc:instance:{identity}")
                self.command(1, "chat", text="/LIBERAR")
                self.wait(lambda: not store.exists(f"npc:instance:{identity}"), "released pet")
                assert identity not in store.smembers(f"player:{self.ids[1]}:pets")
                for index in (1, 2):
                    self.view(
                        index,
                        lambda view: character not in view["world_characters"],
                        "release visible",
                    )
                self.passed(
                    "tamed-owner-orders-restart-release", instance=identity, both_clients=True
                )
                self.wait(
                    lambda: not store.exists(fire),
                    "natural campfire expiry",
                    max(1, until - time.time() + 5),
                )
                for index in (1, 2):
                    self.fire_visible(index, x - 1, y, visible=False)
                    self.screen("campfire-expired", index)
                self.wait(
                    lambda: fire not in store.smembers("world:campfires:2"), "stale index removal"
                )
                self.passed("campfire-expiry-two-clients", original_until=until)
                for index in (1, 2):
                    self.command(index, "soak")
            return self.steps

    def acceptance(steps, seconds, *, graphical, **_):
        required = {
            "campfire-rest-energy",
            "campfire-reconnect-restart",
            "tamed-owner-orders-restart-release",
            "campfire-expiry-two-clients",
        }
        done = {step["id"] for step in steps if step.get("passed")}
        return {
            "kind": "Scoped pet and campfire indexes with two graphical clients",
            "test_execution_passed": graphical and required <= done,
            "missing": sorted(required - done),
        }

    skills_world.MechanicsWorld = ScopedWorld
    skills_world.acceptance = acceptance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build", type=Path)
    parser.add_argument(
        "--scenario",
        choices=("scoped-indexes", "r10", "structure-profile"),
        default="scoped-indexes",
    )
    args = parser.parse_args()
    client, godot, output = args.client.resolve(), args.godot.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(client / "tools"))
    metadata = {
        "kind": "cpython",
        "runtime_executable": sys.executable,
        "source_sha256": source_hashes(),
        "client_engine_execution": "graphical source project",
        "client_native_export": False,
    }
    executable = None
    if args.build:
        build = json.loads(args.build.read_text())
        if (
            build.get("exit_code") != 0
            or not build.get("source_unchanged_during_build")
            or build["source_sha256"] != source_hashes()
        ):
            raise RuntimeError("Candidate does not match the current sources")
        executable = Path(build["executable"])
        if (
            hashlib.file_digest(executable.open("rb"), "sha256").hexdigest()
            != build["executable_sha256"]
        ):
            raise RuntimeError("Candidate executable hash mismatch")
        metadata.update(
            kind="nuitka",
            mode=build["mode"],
            executable=str(executable),
            executable_sha256=build["executable_sha256"],
        )
    (output / "study-runtime.json").write_text(json.dumps(metadata, indent=2) + "\n")
    if args.scenario == "scoped-indexes":
        configure_scenario()
    popen = subprocess.Popen
    launched = []

    def server_process(command, *positional, **keywords):
        if list(command[:3]) == [sys.executable, "-m", "src.run_server"]:
            if executable:
                command = [str(executable), *command[3:]]
            launched.append([str(value) for value in command])
            (output / "study-server-commands.json").write_text(
                json.dumps(launched, indent=2) + "\n"
            )
        return popen(command, *positional, **keywords)

    arguments = [
        str(client / "tools/integration-world.py"),
        "--worker",
        "--source",
        "--server-project",
        str(ROOT),
        "--godot",
        str(godot),
        "--output",
        str(output),
        "--seconds",
        "10",
        "--scenario",
        "skills" if args.scenario == "scoped-indexes" else args.scenario,
        "--client-audio",
        "PulseAudio",
    ]
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="pyao-scoped-graphical-") as temporary:
        try:
            os.chdir(temporary)
            # The worker normally gets this from its parent runner, which is intentionally bypassed here.
            with (
                patch.dict(
                    os.environ,
                    {"PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1"},
                ),
                patch.object(sys, "argv", arguments),
                patch("subprocess.Popen", server_process),
            ):
                runpy.run_path(str(client / "tools/integration-world.py"), run_name="__main__")
        finally:
            os.chdir(previous)
    if not launched:
        raise RuntimeError("No server process was observed")


if __name__ == "__main__":
    main()
