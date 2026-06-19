"""Compatibility exports for the split SeQUeNCe adapter modules."""

from .generation import (
    _eg_action_await,
    _eg_action_request,
    _eg_match_func,
    _install_eg_rule,
    _rule_condition_raw,
)
from .imports import SequenceImports, _import_sequence
from .mapping import inspect_sequence_configuration
from .network import _build_network, _make_router_class
from .purification import (
    _ep_action_await,
    _ep_action_request,
    _ep_condition_await,
    _ep_condition_request,
    _ep_match_func,
    _install_end_to_end_ep_rules,
    _install_ep_rule,
)
from .results import _collect_pairs, _summary_row
from .simulation import run_sequence
from .swapping import (
    _es_action_a,
    _es_action_b,
    _es_condition_a,
    _es_condition_b,
    _es_match_func,
)

__all__ = [
    "SequenceImports",
    "_build_network",
    "_collect_pairs",
    "_eg_action_await",
    "_eg_action_request",
    "_eg_match_func",
    "_ep_action_await",
    "_ep_action_request",
    "_ep_condition_await",
    "_ep_condition_request",
    "_ep_match_func",
    "_es_action_a",
    "_es_action_b",
    "_es_condition_a",
    "_es_condition_b",
    "_es_match_func",
    "_import_sequence",
    "_install_eg_rule",
    "_install_end_to_end_ep_rules",
    "_install_ep_rule",
    "_make_router_class",
    "_rule_condition_raw",
    "_summary_row",
    "inspect_sequence_configuration",
    "run_sequence",
]
