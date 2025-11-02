import logging
from typing import Callable, Any

# Get a logger instance for this module (it won't configure the handler)
logger = logging.getLogger('syncprio.decorators')
logger.setLevel(logging.INFO) # Set default level for the module

# Global Priority Tier Map: Lower tiers are more urgent (SYSTEM is 0).
ROLE_PRIORITY_MAP = {
    'SYSTEM': 0,    # Critical: Initialization, runs before the main loop.
    'ENGINE': 1,    # High Priority: Continuous loop, request/polling.
    'RUNNER': 2,    # Medium Priority: Business logic, on-demand tasks.
    'LPT': 3        # Low Priority Task: Logging, cleanup, maintenance.
}

# --- INTERNAL FUNCTIONS (Decorator Target Logic) ---

def _inject_metadata(obj: Any, key: str, role: str, global_tier: int, local_level: int):
    """
    Inyects SyncPrio-specific scheduling metadata into the decorated object.
    This function ensures the task can be added to the PriorityKernel queue.
    """
    # Check for decoration conflict (e.g., decorating with two different SyncPrio roles)
    if hasattr(obj, '_kernel_role') and getattr(obj, '_kernel_role') != role:
        logger.error(f"Decoration Conflict: Task '{key}' is already decorated with role '{getattr(obj, '_kernel_role')}'.")
        raise ValueError(f"Task '{key}' is already decorated with role '{getattr(obj, '_kernel_role')}'.")

    # The core metadata used by the Kernel for scheduling:
    setattr(obj, '_kernel_role', role)
    setattr(obj, '_global_priority_tier', global_tier)
    setattr(obj, '_local_sequence_level', local_level)
    setattr(obj, '_logical_name', key)
    
    logger.debug(f"Decorated function '{key}' as {role}. Tier: {global_tier}, Level: {local_level}.")

def _decorator_system(seq: int, key: str) -> Callable:
    """Decorator specific for @system, using 'seq' for sequence order."""
    if not (0 <= seq <= 99):
        raise ValueError(f"Sequence level (seq) for SYSTEM must be between 0 and 99.")
    
    def actual_decorator(obj: Any):
        _inject_metadata(obj, key, 'SYSTEM', ROLE_PRIORITY_MAP['SYSTEM'], seq)
        return obj
    return actual_decorator

def _decorator_task(prio: int, key: str, role: str) -> Callable:
    """Decorator for ENGINE, RUNNER, LPT, using 'prio' for local priority."""
    if not (1 <= prio <= 99):
        raise ValueError(f"Priority level (prio) for {role} must be between 1 and 99.")

    def actual_decorator(obj: Any):
        _inject_metadata(obj, key, role, ROLE_PRIORITY_MAP[role], prio)
        return obj
    return actual_decorator

# ------------------------------------
# PUBLIC DECORATORS (The API Interface)
# ------------------------------------

def system(seq: int, key: str) -> Callable:
    """@system(seq: int, key: str) - For critical initialization tasks (Phase 1)."""
    return _decorator_system(seq, key)

def engine(prio: int, key: str) -> Callable:
    """@engine(prio: int, key: str) - High priority loop tasks (Tier 1)."""
    return _decorator_task(prio, key, 'ENGINE')

def runner(prio: int, key: str) -> Callable:
    """@runner(prio: int, key: str) - Medium priority business logic (Tier 2)."""
    return _decorator_task(prio, key, 'RUNNER')

def lpt(prio: int, key: str) -> Callable:
    """@lpt(prio: int, key: str) - Low priority background/cleanup tasks (Tier 3)."""
    return _decorator_task(prio, key, 'LPT')