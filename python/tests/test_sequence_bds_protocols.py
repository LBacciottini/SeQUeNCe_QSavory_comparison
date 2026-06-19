import pathlib
import unittest
from types import SimpleNamespace

from sequence_qsavory_comparison.common.config import load_config
from sequence_qsavory_comparison.sequence.adapter import _import_sequence


CASES_PATH = pathlib.Path(__file__).resolve().parents[2] / "shared" / "testdata" / "werner_protocol_cases.toml"


def _sequence_is_available() -> bool:
    cfg = load_config("shared/configs/default.toml")
    try:
        _import_sequence(cfg["paths"].get("sequence_path"))
    except ModuleNotFoundError:
        return False
    return True


def _werner_fidelity(w: float) -> float:
    return (3 * w + 1) / 4


def _werner_from_fidelity(fidelity: float) -> float:
    return (4 * fidelity - 1) / 3


def _bbpssw_werner_parameter(w: float) -> float:
    return 2 * w * (1 + 2 * w) / (3 * (1 + w * w))


def _load_cases() -> dict[str, object]:
    values: dict[str, object] = {}
    for raw_line in CASES_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, raw_value = [part.strip() for part in line.split("=", 1)]
        if raw_value.startswith("["):
            values[key] = [float(item.strip()) for item in raw_value.strip("[]").split(",")]
        else:
            values[key] = float(raw_value)
    return values


@unittest.skipUnless(_sequence_is_available(), "SeQUeNCe is not installed in this Python environment")
class SequenceBDSProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = load_config("shared/configs/default.toml")
        cls.imports = _import_sequence(cfg["paths"].get("sequence_path"))
        from sequence.components.memory import Memory
        from sequence.constants import BELL_DIAGONAL_STATE_FORMALISM

        cls.Memory = Memory
        cls.BDS = BELL_DIAGONAL_STATE_FORMALISM
        cls.cases = _load_cases()

    def setUp(self):
        self.imports.EntanglementSwappingA.set_formalism(self.BDS)
        self.imports.EntanglementSwappingB.set_formalism(self.BDS)
        self.imports.BBPSSWProtocol.set_formalism(self.BDS)

    def _reset_timeline(self):
        self.timeline = self.imports.Timeline(1, formalism=self.BDS)
        self.nodes = {
            name: SimpleNamespace(name=name, timeline=self.timeline, gate_fid=1.0, meas_fid=1.0)
            for name in ("r1", "r2", "r3")
        }
        self.timeline.entities.update(self.nodes)

    def test_bds_swapping_squares_werner_parameter(self):
        for w in self.cases["w_values"]:
            with self.subTest(w=w):
                self._reset_timeline()
                left_mid, _left_end = self._entangled_pair("left_mid", "r2", "r1", "left_end", w)
                right_mid, _right_end = self._entangled_pair("right_mid", "r2", "r3", "right_end", w)
                protocol = self.imports.EntanglementSwappingA.create(
                    self.nodes["r2"],
                    "swap",
                    left_mid,
                    right_mid,
                    success_prob=1.0,
                )

                output_fidelity = float(protocol.swapping_res()[0])
                output_w = _werner_from_fidelity(output_fidelity)

                self.assertAlmostEqual(output_w, w * w, delta=self.cases["atol"])

    def test_bds_bbpssw_matches_werner_recurrence(self):
        for w in self.cases["w_values"]:
            with self.subTest(w=w):
                self._reset_timeline()
                kept, _remote_kept = self._entangled_pair("kept", "r1", "r2", "remote_kept", w)
                sacrificed, _remote_sacrificed = self._entangled_pair("sacrificed", "r1", "r2", "remote_sacrificed", w)
                protocol = self.imports.BBPSSWProtocol.create(
                    self.nodes["r1"],
                    "bbpssw",
                    kept,
                    sacrificed,
                )
                protocol.remote_node_name = "r2"

                _success_probability, output_state = protocol.purification_res()
                output_w = _werner_from_fidelity(float(output_state[0]))
                expected_w = _bbpssw_werner_parameter(w)

                self.assertAlmostEqual(output_w, expected_w, delta=self.cases["atol"])
                self.assertGreater(output_w, w)

    def _entangled_pair(self, local_name: str, local_node: str, remote_node: str, remote_name: str, w: float):
        local = self.Memory(local_name, self.timeline, _werner_fidelity(w), 1.0, 1.0, -1.0, 500)
        remote = self.Memory(remote_name, self.timeline, _werner_fidelity(w), 1.0, 1.0, -1.0, 500)
        local.entangled_memory = {"node_id": remote_node, "memo_id": remote.name}
        remote.entangled_memory = {"node_id": local_node, "memo_id": local.name}
        local.fidelity = remote.fidelity = _werner_fidelity(w)
        state = [_werner_fidelity(w), (1 - _werner_fidelity(w)) / 3, (1 - _werner_fidelity(w)) / 3, (1 - _werner_fidelity(w)) / 3]
        self.timeline.quantum_manager.set([local.qstate_key, remote.qstate_key], state)
        return local, remote


if __name__ == "__main__":
    unittest.main()
