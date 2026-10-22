"""Mutation tests for the cross-repository protocol audit; no game imports."""

import ast
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "analysis/protocol_inventory.py"
SPEC = importlib.util.spec_from_file_location("protocol_inventory_audit", PATH)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class ProtocolInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.server, self.client = root / "server", root / "client"
        self.policy = {"baseline_commits": {"server": "a" * 40, "client": "b" * 40}, "packets": {}}
        self.reference = {
            "origin": {"commit": "c" * 40},
            "enums": {"client": [], "server": [], "gm": [], "messages": []},
            "writers": {"client": [], "server": []},
            "replacement_commands": {},
            "command_bindings": [],
        }
        self.put(
            self.server,
            "src/network/packet_id.py",
            "from enum import IntEnum\nclass ClientPacketID(IntEnum):\n    WALK=6\n    CAPABILITIES=250\nclass ServerPacketID(IntEnum):\n    CHARACTER_MOVE=32\n    CAPABILITIES=250\n",
        )
        self.put(
            self.server, "src/network/capabilities.py", "class Capability:\n    WORLD_STATE=512\n"
        )
        self.put(self.server, "src/network/packet_framer.py", "# fixture\n")
        self.put(
            self.server,
            "src/network/packet_handlers.py",
            "from src.tasks.walk import TaskWalk\nfrom src.tasks.capabilities import TaskCapabilities\nfrom src.network.packet_id import ClientPacketID\nTASK_HANDLERS: dict = {ClientPacketID.WALK: TaskWalk, ClientPacketID.CAPABILITIES: TaskCapabilities}\n",
        )
        self.put(
            self.server,
            "src/tasks/walk.py",
            "class TaskWalk:\n    async def execute(self):\n        await self.map.move()\n",
        )
        self.put(
            self.server,
            "src/tasks/capabilities.py",
            "class TaskCapabilities:\n    async def execute(self):\n        await self.connection.send_reply()\n",
        )
        self.put(
            self.server,
            "src/network/messages.py",
            "from src.network.packet_id import ServerPacketID\ndef build_move():\n    return PacketBuilder().add_byte(ServerPacketID.CHARACTER_MOVE).add_int16(4).to_bytes()\ndef build_capabilities():\n    return bytes([ServerPacketID.CAPABILITIES])\nasync def tick():\n    await send(build_move())\n    await send(build_capabilities())\n",
        )
        for path, name in [
            ("src/tasks/task_skill_action.py", "ACTION_FIELDS"),
            ("src/services/world/actions.py", "ACTION_FIELDS"),
            ("src/services/expansion/service.py", "EXPANSION_FIELDS"),
        ]:
            self.put(self.server, path, f"{name}: dict = {{}}\n")
        self.put(
            self.client,
            "common/enums/enums.gd",
            "enum ClientPacketID {Walk = 6}\nenum ServerPacketID {CharacterMove = 32}\nenum EGMCommands {WARP_CHAR = 11}\nenum Messages {NPCSwing = 0}\n",
        )
        self.put(
            self.client,
            "engine/autoload/game_protocol.gd",
            "# Long comments must not move evidence to another function.\nstatic func WriteWalk(heading):\n\tif not _can_write(6): return\n\t_writer.put_u8(6)\n\t_writer.put_u8(heading)\n",
        )
        self.put(
            self.client,
            "network/client_capabilities.gd",
            "const PACKET_ID := 250\nconst NEGOTIATION_TIMEOUT_SECONDS := 30.0\nfunc begin():\n\tpacket.put_u8(PACKET_ID)\n\treturn packet.data_array\nfunc accept(data):\n\tenabled = data[1]\n\treturn enabled > 0\n",
        )
        self.put(
            self.client,
            "network/message_dispatcher.gd",
            'func dispatch_stream(stream):\n\tvar packetId = stream.get_u8()\n\tmatch packetId:\n\t\tEnums.ServerPacketID.CharacterMove:\n\t\t\t_emit(&"_HandleMove", CharacterMove.new(stream))\n',
        )
        self.put(
            self.client,
            "network/commands/CharacterMove.gd",
            "class_name CharacterMove\nfunc Deserialize(reader):\n\tindex = reader.get_16()\n",
        )
        self.put(self.client, "network/packet_framer.gd", "# fixture\n")
        self.put(self.client, "screens/login_screen.gd", "func receive():\n\tpass\n")
        self.put(self.client, "screens/character_creation_screen.gd", "func receive():\n\tpass\n")
        self.put(
            self.client,
            "screens/game_screen.gd",
            "func _OnDecodedMessage(handler, payload):\n\tcall(handler, payload)\nfunc _HandleMove(value):\n\tcharacter.position = value.position\n",
        )
        self.put(self.client, "screens/input.gd", "func walk():\n\tGameProtocol.WriteWalk(1)\n")
        self.contract = {
            "directions": {
                "client": {
                    "6": {
                        "name": "WALK",
                        "status": "supported",
                        "fields": [{"name": "heading", "type": "u8"}],
                    },
                    "250": {"name": "CAPABILITIES", "status": "supported", "fields": []},
                },
                "server": {
                    "32": {
                        "name": "CHARACTER_MOVE",
                        "status": "supported",
                        "fields": [{"name": "index", "type": "i16"}],
                    },
                    "250": {"name": "CAPABILITIES", "status": "supported", "fields": []},
                },
            },
            "capabilities": {
                "response_timeout_client_seconds": 30,
                "mask_bits": {"world_state": 512},
            },
            "compatibility": {"state": "current"},
        }
        self.sync_contract()

    @staticmethod
    def put(root, name, text):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def sync_contract(self):
        for root, name in [
            (self.server, "src/network/protocol/contract.json"),
            (self.client, "protocol/contract.json"),
        ]:
            self.put(root, name, json.dumps(self.contract))

    def generate(self):
        return audit.inventory(self.server, self.client, self.policy, self.reference)

    @staticmethod
    def packet(result, direction, number):
        return next(
            row
            for row in result["packets"]
            if row["direction"] == direction and row["id"] == number
        )

    def test_stable_inventory_does_not_credit_unexecuted_packets(self):
        first = self.generate()
        self.assertEqual(first, self.generate())
        self.assertEqual(first["diagnostics"], [])
        self.assertEqual(self.packet(first, "client_to_server", 6)["status"], "wired_not_exercised")

    def test_changed_enum_id_is_detected(self):
        path = self.server / "src/network/packet_id.py"
        path.write_text(path.read_text().replace("CHARACTER_MOVE=32", "CHARACTER_MOVE=33"))
        result = self.generate()
        self.assertIn("enum_contract_mismatch", {row["kind"] for row in result["diagnostics"]})
        self.assertIn("writer_outside_contract", {row["kind"] for row in result["diagnostics"]})

    def test_missing_handler_is_not_counted_as_operational(self):
        path = self.server / "src/network/packet_handlers.py"
        path.write_text(path.read_text().replace("ClientPacketID.WALK: TaskWalk, ", ""))
        row = self.packet(self.generate(), "client_to_server", 6)
        self.assertEqual(row["status"], "emitter_without_receiver")

    def test_raw_client_writer_outside_contract_is_detected(self):
        path = self.client / "engine/autoload/game_protocol.gd"
        path.write_text(path.read_text().replace("_writer.put_u8(6)", "_writer.put_u8(249)"))
        result = self.generate()
        self.assertTrue(
            any(
                d["kind"] == "writer_outside_contract" and d["id"] == 249
                for d in result["diagnostics"]
            )
        )

    def test_raw_server_writer_outside_contract_is_detected(self):
        path = self.server / "src/network/messages.py"
        path.write_text(path.read_text().replace("ServerPacketID.CHARACTER_MOVE", "249"))
        result = self.generate()
        self.assertTrue(
            any(
                d["kind"] == "writer_outside_contract" and d["id"] == 249
                for d in result["diagnostics"]
            )
        )

    def test_noop_consumer_is_not_an_implementation(self):
        path = self.client / "screens/game_screen.gd"
        path.write_text(path.read_text().replace("character.position = value.position", "pass"))
        self.assertEqual(
            self.packet(self.generate(), "server_to_client", 32)["status"], "stub_or_noop"
        )

    def test_changed_field_width_requires_review(self):
        path = self.client / "engine/autoload/game_protocol.gd"
        path.write_text(path.read_text().replace("put_u8(heading)", "put_16(heading)"))
        row = self.packet(self.generate(), "client_to_server", 6)
        self.assertEqual(row["layout_review"][0]["status"], "different_requires_review")

    def test_comments_do_not_create_packets_or_shift_evidence(self):
        path = self.client / "engine/autoload/game_protocol.gd"
        path.write_text("# _writer.put_u8(249)\n" + path.read_text())
        result = self.generate()
        self.assertFalse(any(d["kind"] == "writer_outside_contract" for d in result["diagnostics"]))
        self.assertEqual(self.packet(result, "client_to_server", 6)["serialization"][0]["line"], 3)

    def test_contract_divergence_is_fatal(self):
        self.put(self.client, "protocol/contract.json", "{}")
        with self.assertRaisesRegex(ValueError, "contratos"):
            self.generate()

    def test_chained_builders_preserve_execution_order(self):
        node = ast.parse(
            "def f():\n return PacketBuilder().add_byte(32).add_int16(4).to_bytes()\n"
        ).body[0]
        function = audit.Function("server", "fixture", "f", 1, 2, "", node)
        self.assertEqual(function.primitives(), ["u8", "i16"])

    def test_returning_an_effect_is_not_a_noop(self):
        node = ast.parse("def f():\n return move()\n").body[0]
        self.assertFalse(audit.Function("server", "fixture", "f", 1, 2, "", node).stub())

    def test_inline_dispatch_labels_have_effect_evidence(self):
        self.put(
            self.client,
            "screens/game_screen.gd",
            'func _OnDecodedMessage(handler, payload):\n\tmatch handler:\n\t\t&"_HandleMove": character.position = payload.position\n',
        )
        row = self.packet(self.generate(), "server_to_client", 32)
        self.assertEqual(row["ui_support"], "effect_route_found")
        self.assertEqual(row["effect_or_ui"][0]["symbol"], "_OnDecodedMessage/_HandleMove")

    def test_same_named_method_in_unrelated_node_cannot_fake_a_consumer(self):
        path = self.client / "screens/game_screen.gd"
        path.write_text(path.read_text().replace("character.position = value.position", "pass"))
        self.put(self.client, "ui/unrelated.gd", "func _HandleMove(value):\n\tmove(value)\n")
        self.assertEqual(
            self.packet(self.generate(), "server_to_client", 32)["status"], "stub_or_noop"
        )

    def test_negotiated_schema_changes_are_inventoried(self):
        self.put(
            self.server,
            "src/tasks/task_skill_action.py",
            'ACTION_FIELDS: dict = {"work": {"skill": int}}\n',
        )
        result = self.generate()
        action = next(row for row in result["subtypes"] if row["subtype"] == "work")
        self.assertEqual(action["fields"], {"skill": "int"})
        self.assertEqual(action["requires_capability"], 256)
        self.assertEqual(action["dynamic_verification"], "not_credited_by_static_analysis")

    def test_binary_payload_constants_do_not_become_packet_ids(self):
        path = self.server / "src/network/messages.py"
        path.write_text(
            path.read_text()
            .replace("def build_move():", "VERSION=249\ndef build_move():")
            .replace(".add_int16(4)", ".add_byte(VERSION)")
        )
        self.assertFalse(
            any(
                d["kind"] == "writer_outside_contract" and d["id"] == 249
                for d in self.generate()["diagnostics"]
            )
        )

    def test_shifted_numeric_extension_receiver_is_detected(self):
        self.put(
            self.client,
            "network/message_dispatcher.gd",
            'func dispatch_stream(stream):\n\tvar packetId = stream.get_u8()\n\tif packetId == 33:\n\t\t_emit(&"_HandleMove", CharacterMove.new(stream))\n\t\treturn\n',
        )
        self.assertEqual(
            self.packet(self.generate(), "server_to_client", 32)["status"],
            "emitter_without_receiver",
        )

    def test_changed_source_withdraws_historical_dynamic_credit(self):
        folder = self.server / audit.CATALOG
        folder.mkdir(parents=True)
        result = {
            "passed": True,
            "clients": 2,
            "native_export": True,
            "tls": True,
            "server_commit": "a" * 40,
            "client_commit": "b" * 40,
            "acceptance": {"required": ["move"]},
            "long_acceptance": False,
        }
        (folder / "representative-result.json").write_text(json.dumps(result))
        (folder / "representative-scenarios.json").write_text(
            json.dumps([{"id": "move", "passed": True}])
        )
        path = self.client / "engine/autoload/game_protocol.gd"
        proof = {
            "commits": {"server": "a" * 40, "client": "b" * 40},
            "result_sha256": audit.sha(folder / "representative-result.json"),
            "scenarios_sha256": audit.sha(folder / "representative-scenarios.json"),
            "runtime_inputs": [
                {
                    "repository": "client",
                    "path": "engine/autoload/game_protocol.gd",
                    "sha256": audit.sha(path),
                }
            ],
            "packet_cases": {"client": {"6": ["move"]}},
        }
        (folder / "representative.json").write_text(json.dumps(proof))
        self.assertEqual(
            self.packet(self.generate(), "client_to_server", 6)["status"], "operational_end_to_end"
        )
        path.write_text(path.read_text() + "\n# newer code\n")
        changed = self.generate()
        self.assertEqual(
            self.packet(changed, "client_to_server", 6)["status"], "wired_not_exercised"
        )
        self.assertEqual(
            changed["representative_validation"]["status"], "historical_source_changed"
        )

    def test_quoted_call_name_cannot_fake_production_usage(self):
        self.put(
            self.client,
            "screens/input.gd",
            'func example():\n\tprint("GameProtocol.WriteWalk(1)")\n',
        )
        self.assertEqual(
            self.packet(self.generate(), "client_to_server", 6)["production_callers"], []
        )


if __name__ == "__main__":
    unittest.main()
