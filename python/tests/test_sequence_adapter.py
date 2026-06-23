import unittest
from unittest.mock import patch
from types import SimpleNamespace

from sequence_qsavory_comparison.common.config import load_config, resolve_config
from sequence_qsavory_comparison.sequence.adapter import (
    WERNER_BBPSSW_FORMALISM,
    _build_network,
    _ep_action_await,
    _ep_action_request,
    _ep_condition_await,
    _ep_condition_request,
    _es_action_a,
    _install_end_to_end_ep_rules,
    _summary_row,
    inspect_sequence_configuration,
    install_werner_bbpssw_protocol,
)


class SequenceAdapterInspectionTests(unittest.TestCase):
    def test_inspection_matches_shared_config(self):
        cfg = load_config("shared/configs/default.toml")
        resolved = resolve_config(cfg)
        applied = inspect_sequence_configuration(cfg)

        self.assertEqual(applied["memory_counts"]["r1"], cfg["memories"]["r1_count"])
        self.assertEqual(applied["formalism"]["quantum_manager"], "ket_vector")
        self.assertEqual(applied["formalism"]["swapping"], "ket_vector_with_ideal_fidelity_update")
        self.assertEqual(applied["formalism"]["purification"], WERNER_BBPSSW_FORMALISM)
        self.assertEqual(applied["rules"]["flow1_r1_slots"], cfg["resource_reservation"]["flow1"]["r1_slots"])
        self.assertEqual(applied["rules"]["flow2_r2_right_slots"], cfg["resource_reservation"]["flow2"]["r2_right_slots"])
        self.assertEqual(applied["channels"]["classical_delay_ps"], resolved["derived"]["classical_delay_ps"])
        self.assertEqual(applied["detectors"]["efficiency"], cfg["detectors"]["efficiency"])
        self.assertEqual(applied["memory_parameters"]["efficiency"], resolved["derived"]["source_transmissivity"])
        self.assertEqual(applied["memory_parameters"]["coherence_time_s"], -1.0)
        self.assertEqual(applied["memory_parameters"]["decoherence_rate_hz"], 0.0)
        self.assertFalse(applied["memory_parameters"]["cutoff_enabled"])
        self.assertEqual(
            applied["barrett_kok_timing"]["effective_attempt_time_s"],
            resolved["derived"]["barrett_kok_effective_attempt_time_s"],
        )
        self.assertEqual(applied["rules"]["purification_scope"], "end_to_end_only")
        self.assertEqual(applied["rules"]["purification_request_node"], "r1")
        self.assertEqual(applied["rules"]["purification_response_node"], "r3")
        self.assertEqual(applied["rules"]["purification_request_slots"], cfg["resource_reservation"]["flow2"]["r1_slots"])
        self.assertEqual(applied["rules"]["purification_response_slots"], cfg["resource_reservation"]["flow2"]["r3_slots"])
        self.assertEqual(applied["rules"]["swap_fidelity_model"], "ideal")

    def test_end_to_end_purification_rules_target_only_r1_r3(self):
        flow2 = load_config("shared/configs/default.toml")["resource_reservation"]["flow2"]
        r1 = _FakeNode()
        r3 = _FakeNode()

        _install_end_to_end_ep_rules(_FakeRule, r1, r3, flow2, target_fidelity=0.9)

        self.assertEqual(len(r1.resource_manager.rules), 1)
        self.assertEqual(len(r3.resource_manager.rules), 1)
        self.assertIs(r1.resource_manager.rules[0].action, _ep_action_request)
        self.assertIs(r1.resource_manager.rules[0].condition, _ep_condition_request)
        self.assertEqual(r1.resource_manager.rules[0].condition_args["remote_node"], "r3")
        self.assertEqual(
            [r1.resource_manager.rules[0].condition_args["index_lower"], r1.resource_manager.rules[0].condition_args["index_upper"]],
            flow2["r1_slots"],
        )
        self.assertIs(r3.resource_manager.rules[0].action, _ep_action_await)
        self.assertIs(r3.resource_manager.rules[0].condition, _ep_condition_await)
        self.assertEqual(r3.resource_manager.rules[0].condition_args["remote_node"], "r1")
        self.assertEqual(
            [r3.resource_manager.rules[0].condition_args["index_lower"], r3.resource_manager.rules[0].condition_args["index_upper"]],
            flow2["r3_slots"],
        )

    def test_purification_conditions_reject_elementary_pairs(self):
        target_fidelity = 0.9
        args = {"index_lower": 10, "index_upper": 19, "target_fidelity": target_fidelity, "remote_node": "r3"}
        elementary = _memory_info(10, "ENTANGLED", "r2", 0.8)
        end_to_end_a = _memory_info(11, "ENTANGLED", "r3", 0.8)
        end_to_end_b = _memory_info(12, "ENTANGLED", "r3", 0.8)

        self.assertEqual(_ep_condition_request(elementary, [elementary, end_to_end_a, end_to_end_b], args), [])
        self.assertEqual(_ep_condition_request(end_to_end_a, [elementary, end_to_end_a, end_to_end_b], args), [end_to_end_a, end_to_end_b])
        self.assertEqual(_ep_condition_await(elementary, [elementary], args), [])
        self.assertEqual(_ep_condition_await(end_to_end_a, [end_to_end_a], args), [end_to_end_a])

    def test_summary_completion_accepts_one_raw_flow2_pair(self):
        rows = [
            {"flow": "flow2", "delivery_time_s": 0.1, "fidelity": 0.9, "status": "ENTANGLED"},
            {"flow": "flow2", "delivery_time_s": 0.2, "fidelity": 0.95, "status": "PURIFIED"},
            {"flow": "flow2", "delivery_time_s": 0.3, "fidelity": 0.96, "status": "PURIFIED"},
            {"flow": "flow1", "delivery_time_s": 0.4, "fidelity": 0.97, "status": "ENTANGLED"},
        ]

        summary = _summary_row("sequence", 1, "completed", 1.0, rows, 2, require_purified_flow2=True)

        self.assertEqual(summary["flow2_delivered"], 3)
        self.assertEqual(summary["target_completed"], True)
        self.assertEqual(summary["completion_time_s"], 0.2)
        self.assertAlmostEqual(summary["flow2_mean_fidelity"], (0.9 + 0.95 + 0.96) / 3)

    def test_summary_requires_enough_purified_flow2_pairs(self):
        rows = [
            {"flow": "flow2", "delivery_time_s": 0.1, "fidelity": 0.9, "status": "ENTANGLED"},
            {"flow": "flow2", "delivery_time_s": 0.2, "fidelity": 0.95, "status": "PURIFIED"},
            {"flow": "flow2", "delivery_time_s": 0.3, "fidelity": 0.91, "status": "ENTANGLED"},
        ]

        summary = _summary_row("sequence", 1, "completed", 1.0, rows, 3, require_purified_flow2=True)

        self.assertEqual(summary["flow2_delivered"], 3)
        self.assertEqual(summary["target_completed"], False)
        self.assertEqual(summary["completion_time_s"], "")

    def test_swap_action_forces_ideal_degradation_when_supported(self):
        left = SimpleNamespace(name="r2.mem0")
        right = SimpleNamespace(name="r2.mem1")
        infos = [
            SimpleNamespace(memory=left, remote_node="r1", remote_memo="r1.mem0"),
            SimpleNamespace(memory=right, remote_node="r3", remote_memo="r3.mem0"),
        ]
        fake_imports = SimpleNamespace(
            EntanglementSwappingA=_FakeSwapFactory,
            EntanglementSwappingB=object,
        )

        with patch("sequence_qsavory_comparison.sequence.swapping.import_sequence", return_value=fake_imports):
            protocol, *_ = _es_action_a(infos, {"succ_prob": 1.0})

        self.assertEqual(protocol.degradation, 1.0)

    def test_build_network_leaves_quantum_manager_formalism_compatible_with_barrett_kok(self):
        cfg = load_config("shared/configs/default.toml")
        resolved = resolve_config(cfg)
        imports = _FakeSequenceImports()

        timeline, *_ = _build_network(resolved, imports, seed=3)

        self.assertIsNone(imports.EntanglementSwappingA.formalism)
        self.assertIsNone(imports.EntanglementSwappingB.formalism)
        self.assertIsNone(imports.BBPSSWProtocol.formalism)
        self.assertIsNone(timeline.formalism)

    def test_install_werner_bbpssw_protocol_selects_adapter_protocol(self):
        imports = _FakeSequenceImports()

        install_werner_bbpssw_protocol(imports)

        self.assertEqual(imports.BBPSSWProtocol.formalism, WERNER_BBPSSW_FORMALISM)
        self.assertIn(WERNER_BBPSSW_FORMALISM, imports.BBPSSWProtocol.protocols)


class _FakeResourceManager:
    def __init__(self):
        self.rules = []

    def load(self, rule):
        self.rules.append(rule)


class _FakeNode:
    def __init__(self):
        self.resource_manager = _FakeResourceManager()


class _FakeRule:
    def __init__(self, priority, action, condition, action_args, condition_args):
        self.priority = priority
        self.action = action
        self.condition = condition
        self.action_args = action_args
        self.condition_args = condition_args


class _FakeSwapFactory:
    @staticmethod
    def create(*args, **kwargs):
        return SimpleNamespace(degradation=0.95)


class _FakeFormalismFactory:
    formalism = None

    @classmethod
    def set_formalism(cls, formalism):
        cls.formalism = formalism


class _FakeBBPSSWFactory(_FakeFormalismFactory):
    protocols = {WERNER_BBPSSW_FORMALISM}

    @classmethod
    def list_protocols(cls):
        return list(cls.protocols)


class _FakeTimeline:
    def __init__(self, stop_time, formalism=None):
        self.stop_time = stop_time
        self.formalism = formalism


class _FakeMemoryArray:
    def __init__(self):
        self.params = {}

    def update_memory_params(self, key, value):
        self.params[key] = value


class _FakeQuantumRouter:
    def __init__(self, name, timeline, memo_size):
        self.name = name
        self.timeline = timeline
        self.memo_size = memo_size
        self.protocols = []
        self._memory_array = _FakeMemoryArray()

    def get_components_by_type(self, component_type):
        if component_type == "MemoryArray":
            return [self._memory_array]
        return []

    def send_qubit(self, dst, photon):
        return None

    def set_seed(self, seed):
        self.seed = seed


class _FakeBSMNode:
    def __init__(self, name, timeline, connected_nodes, component_templates=None):
        self.name = name
        self.timeline = timeline
        self.connected_nodes = connected_nodes
        self.component_templates = component_templates or {}

    def set_seed(self, seed):
        self.seed = seed


class _FakeClassicalChannel:
    def __init__(self, name, timeline, distance, delay):
        self.name = name

    def set_ends(self, node, remote_name):
        return None


class _FakeQuantumChannel:
    def __init__(self, name, timeline, attenuation, distance, frequency):
        self.name = name

    def set_ends(self, node, remote_name):
        return None


class _FakeSequenceImports:
    BELL_DIAGONAL_STATE_FORMALISM = "bell_diagonal"
    Timeline = _FakeTimeline
    QuantumRouter = _FakeQuantumRouter
    BSMNode = _FakeBSMNode
    ClassicalChannel = _FakeClassicalChannel
    QuantumChannel = _FakeQuantumChannel
    Rule = _FakeRule
    ResourceManager = lambda self, node, memory_array_name: _FakeResourceManager()
    MemoryInfo = object
    EntanglementGenerationA = object
    BBPSSWProtocol = _FakeBBPSSWFactory
    EntanglementSwappingA = type("FakeEntanglementSwappingA", (_FakeFormalismFactory,), {})
    EntanglementSwappingB = type("FakeEntanglementSwappingB", (_FakeFormalismFactory,), {})

    def __init__(self):
        self.BBPSSWProtocol.formalism = None
        self.EntanglementSwappingA.formalism = None
        self.EntanglementSwappingB.formalism = None


def _memory_info(index, state, remote_node, fidelity):
    return SimpleNamespace(index=index, state=state, remote_node=remote_node, fidelity=fidelity)


if __name__ == "__main__":
    unittest.main()
