"""Reject benchmarks that silently change interpreter semantics or results."""

from copy import deepcopy
import unittest

from tools.analysis.nuitka_study import validate_probes


class ProbeComparabilityTests(unittest.TestCase):
    def fixture(self):
        return {
            "runtime": {
                "version": "3.14.8",
                "gil_enabled": True,
                "jit_enabled": False,
                "optimize": 0,
                "machine": "x86_64",
            },
            "kernels": {"movement": {"checksum": 42}},
        }

    def test_identical_inputs_are_comparable(self):
        baseline = self.fixture()
        self.assertTrue(validate_probes([baseline, deepcopy(baseline)])["same_kernel_checksums"])

    def test_changed_gil_jit_flags_or_version_are_not_a_compilation_speedup(self):
        for field, value in (
            ("gil_enabled", False),
            ("jit_enabled", True),
            ("optimize", 2),
            ("version", "3.14.0"),
        ):
            with self.subTest(field=field):
                baseline, candidate = self.fixture(), self.fixture()
                candidate["runtime"][field] = value
                with self.assertRaisesRegex(RuntimeError, "runtimes differ"):
                    validate_probes([baseline, candidate])

    def test_wrong_combat_result_is_not_accepted_as_a_faster_kernel(self):
        baseline, candidate = self.fixture(), self.fixture()
        candidate["kernels"]["movement"]["checksum"] = 0
        with self.assertRaisesRegex(RuntimeError, "results differ"):
            validate_probes([baseline, candidate])


if __name__ == "__main__":
    unittest.main()
