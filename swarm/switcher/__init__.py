"""Auto Model Switcher v2 — integrated into agent-swarm.

This package wraps the auto-model-switcher from
https://github.com/farhanic017/auto-model-switcher

Original author: Farhan Dhrubo <farhaiee123@gmail.com>
License: GPL-3.0
"""

from swarm.switcher.switcher import (
    discover_providers,
    discover_local_models,
    build_chain,
    check_model,
    check_all_parallel,
    score_model,
    detect_task,
    get_model_specialty,
    update_opencode_config,
    set_active,
    get_active,
    mark_depleted,
    mark_recovered,
    is_depleted,
    load_state,
    save_state,
    get_recovery_eta,
    save_context,
    load_context,
    build_mcp_handoff,
    log,
)

from swarm.switcher.bridge import SwitcherBridge, resolve_provider_and_model

__all__ = [
    "SwitcherBridge",
    "resolve_provider_and_model",
    "discover_providers",
    "discover_local_models",
    "build_chain",
    "check_model",
    "check_all_parallel",
    "score_model",
    "detect_task",
    "get_model_specialty",
    "update_opencode_config",
    "set_active",
    "get_active",
    "mark_depleted",
    "mark_recovered",
    "is_depleted",
    "load_state",
    "save_state",
    "get_recovery_eta",
    "save_context",
    "load_context",
    "build_mcp_handoff",
    "log",
]
