"""Experimental entry point; never installed or published as the server CLI."""

import json
import sys


def main():
    if sys.argv[1:2] == ["--study-kernels"]:
        from tools.analysis.interpreter_study import probe

        result = probe(101, 1000)
        result["compiled_entry"] = "__compiled__" in globals()
        result["compiled_kernels"] = {
            name: "__compiled__" in vars(sys.modules[name])
            for name in (
                "src.game.coordinate_mask",
                "src.game.map_manager",
                "src.models.npc",
                "src.network.msg_character",
                "src.services.combat.physical_plan",
                "src.utils.ground_state",
            )
        }
        print(json.dumps(result))
    else:
        from src.run_server import main as server_main

        server_main()


if __name__ == "__main__":
    main()
