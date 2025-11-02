from typing import Dict, Any, List, Tuple, Callable
import time
import sys
import logging
import random # Standard library for Jitter (random delay)
from .decorators import ROLE_PRIORITY_MAP

# Setup Logger for the Kernel (Adheres to library logging standards)
logger = logging.getLogger('syncprio')
logger.setLevel(logging.INFO) 

# --- QUANTUM DEFINITION ---
# 50ms: Max time a continuous task can run before being considered "blocked" or "hanging".
MAX_EXECUTION_QUANTUM = 0.05 

# --- RESILIENCE DEFINITIONS (JITTER & BACKOFF) ---
# Maximum penalty weight (sends task to the absolute back of the queue: LPT max weight is 399).
MAX_PENALTY_WEIGHT = 399
# Base minimum delay (in seconds) for the exponential backoff calculation.
BASE_BACKOFF_TIME = 0.5 
# Upper limit for the random delay (Jitter) to prevent excessively long waits.
MAX_DELAY_CAP = 30.0 

# Max consecutive failures per role before permanent discard (Critical policy).
ROLE_MAX_FAILS = {
    'ENGINE': 5, # High-priority tasks get more retries
    'RUNNER': 3, 
    'LPT': 2     # Low-priority tasks are discarded sooner
}

# --- ADAPTOR CONDICIONAL (Conditional Adapter) ---
try:
    from routless.core import load 
    routless_LOADER = load
    logger.info("Kernel: 'routless' loader activated. Darkness Mode supported.")
except ImportError:
    routless_LOADER = None
    logger.warning("Kernel: 'routless' is not installed. Darkness Mode (token execution) is NOT supported.")

# Definition of an Execution Task (8 elements for Resilience)
# (weight, global_tier, local_level, logical_name, args, fail_count, unblock_time, weight_original)
# This tuple is the core data structure of the monothread scheduler.
Task = Tuple[int, int, int, str, Dict[str, Any], int, float, int]


class PriorityKernel:
    """
    PriorityKernel: A monothread, synchronous scheduler that executes tasks 
    based on priority tiers (SYSTEM, ENGINE, RUNNER, LPT). 
    
    Implements Exponential Backoff with Jitter for high resilience against 
    external service failures (APIs, network) while maintaining a single thread.
    """
    
    def __init__(self):
        """Initializes the PriorityKernel, setting up the task queue."""
        self.task_queue: List[Task] = []
        self.is_running = False
        logger.info("Kernel: PriorityKernel initialized.")
        
    def _calculate_weight(self, global_tier: int, local_level: int) -> int:
        """Calculates the total weight for sorting. Lower weight means higher priority."""
        return (global_tier * 100) + local_level

    def add_task(self, task_reference: Any, args: Dict[str, Any] = None):
        """
        Adds a task to the monothread execution queue. 
        It injects resilience metadata (fail_count, unblock_time, weight_original).
        """
        args = args or {}
        # ... (Validation and Metadata resolution logic remains the same) ...

        # --- DUAL MODE CHECK ---
        if isinstance(task_reference, str):
            if routless_LOADER is None:
                logger.error(f"Kernel: Attempted 'Darkness Mode' for '{task_reference}', but 'routless' is missing.")
                raise RuntimeError("Cannot use string 'key' references without the 'routless' library.")
            logical_name = task_reference
            # NOTE: We can't resolve the object here, task_obj is None, which is fine.
        elif callable(task_reference):
            task_obj = task_reference
            logical_name = getattr(task_obj, '_logical_name', task_obj.__name__)
        else:
            logger.error(f"Kernel: Invalid task reference type: {type(task_reference)}.")
            raise TypeError("Task must be a string (token) or a callable function/class.")

        # --- METADATA RETRIEVAL (Must check if it's a callable object) ---
        if callable(task_reference):
            if not hasattr(task_obj, '_kernel_role'):
                logger.error(f"Kernel: Task '{logical_name}' is missing SyncPrio metadata (not decorated).")
                raise ValueError(
                    f"Task '{logical_name}' was not decorated with a SyncPrio primitive."
                )
            
            role = getattr(task_obj, '_kernel_role')
            global_tier = getattr(task_obj, '_global_priority_tier')
            local_level = getattr(task_obj, '_local_sequence_level')
        else:
            # Placeholder for dynamic loading (Minimal setup for string keys)
            role = "DARKNESS_MODE"
            global_tier = 4 # Default tier if metadata cannot be read statically
            local_level = 99
        
        weight = self._calculate_weight(global_tier, local_level)

        # --- RESILIENCE INITIALIZATION ---
        fail_count = 0
        unblock_time = 0.0 # Time when the task can be re-executed
        weight_original = weight # Preserve original weight for restoration
        
        new_task: Task = (
            weight, 
            global_tier, 
            local_level, 
            logical_name, 
            args,
            fail_count,           
            unblock_time,         
            weight_original       
        )
        
        self.task_queue.append(new_task)
        self.task_queue.sort(key=lambda x: x[0])
        
        logger.debug(f"Kernel: Task added: '{logical_name}' (Weight: {weight}, Role: {role}).")


    def run_system_tasks(self, system_task_keys: List[str]):
        """Phase 1: Executes all @system tasks in strict sequence order (seq)."""
        logger.info("\n--- PHASE 1: Running SYSTEM Tasks (Strict Sequence) ---")
        # ... (System task execution logic remains the same) ...
        logger.info("--- PHASE 1 COMPLETE. Kernel ready for the loop. ---")


    def run_loop(self):
        """
        Phase 2: The main monothread loop with QUANTUM and RESILIENCE logic.
        """
        self.is_running = True
        logger.info("\n--- PHASE 2: Starting Monothread Loop (Resilient) ---")
        
        while self.is_running or self.task_queue:
            if not self.task_queue:
                time.sleep(0.01) # Small sleep to reduce CPU usage when idle
                continue
            
            # Unpack 8 elements for Resilience State Check
            # (0:weight, 1:global_tier, 2:local_level, 3:logical_name, 4:args, 5:fail_count, 6:unblock_time, 7:weight_original)
            (weight, global_tier, local_level, logical_name, args, 
             fail_count, unblock_time, weight_original) = self.task_queue.pop(0)
             
            role = next(k for k, v in ROLE_PRIORITY_MAP.items() if v == global_tier)
            
            # --- JITTER/BACKOFF DELAY CHECK (Core Resilience Logic) ---
            if unblock_time > time.time():
                # Task is penalized: Requeue immediately with the same state to wait out the delay.
                logger.debug(f"Kernel: [DELAY] Role: {role}, Name: {logical_name} is in backoff ({unblock_time - time.time():.2f}s left).")
                
                self.task_queue.append((
                    weight, global_tier, local_level, logical_name, args, 
                    fail_count, unblock_time, weight_original
                ))
                self.task_queue.sort(key=lambda x: x[0])
                continue # Skip execution, allow next task to run
            
            # 1. RESOLVE TASK FROM ROUTLESS (Simulating dynamic loading)
            task_func = None
            if routless_LOADER:
                try:
                    task_func = routless_LOADER(logical_name)
                except Exception as e:
                     logger.error(f"Kernel: [RESOLVE FAIL] Failed to resolve task '{logical_name}': {e}. Dropping task.")
                     continue
            # If not using routless, task_func resolution logic for callables would go here.

            # 2. EXECUTE TASK WITH QUANTUM CHECK
            start_time = time.time()
            
            try:
                logger.debug(f"Kernel: [EXEC] Role: {role}, Name: {logical_name}. Attempt #{fail_count + 1}")
                # NOTE: Execution logic must handle case where task_func is not found if not using routless.
                if task_func:
                    task_func(**args)
                
            except Exception as e:
                # --- TASK CRASH & RESILIENCE PENALTY LOGIC ---
                
                max_fails = ROLE_MAX_FAILS.get(role, 1)
                fail_count += 1
                
                if fail_count >= max_fails:
                    # Policy: Maximum retry threshold exceeded. Permanent discard.
                    logger.critical(f"Kernel: [FATAL DISCARD] 🚨 Role: {role}, Name: {logical_name} failed {fail_count} times. Discarded permanently.")
                    continue 
                
                # Exponential Backoff Calculation
                exponential_delay = BASE_BACKOFF_TIME * (2 ** fail_count)
                
                # Jitter: Random delay between 0 and Exponential, capped by MAX_DELAY_CAP.
                delay = min(random.uniform(0, exponential_delay), MAX_DELAY_CAP)
                
                unblock_time = time.time() + delay
                
                # Penalty: Degrade priority to the worst possible weight (399).
                weight_new = MAX_PENALTY_WEIGHT 
                
                logger.error(f"Kernel: [FAIL PENALTY] Role: {role}, Name: {logical_name} failed: {e}. Requeuing with {delay:.2f}s Jitter (New Weight: {weight_new}).")
                
                # Requeue the task with the new penalized state
                self.task_queue.append((
                    weight_new, global_tier, local_level, logical_name, args, 
                    fail_count, unblock_time, weight_original
                ))
                self.task_queue.sort(key=lambda x: x[0])
                continue

            # 3. CHECK QUANTUM (The Hang Resilience)
            elapsed = time.time() - start_time
            
            if elapsed > MAX_EXECUTION_QUANTUM:
                # Task blocked or hung, remove from the queue.
                logger.critical(f"Kernel: [BLOCKED] 🛑 Role: {role}, Name: {logical_name} exceeded quantum ({MAX_EXECUTION_QUANTUM:.4f}s). DROPPING TASK.")
                continue 
            
            # 4. SUCCESS: REQUEUE LOGIC
            if role in ['ENGINE', 'RUNNER', 'LPT']:
                
                # --- RESTORATION LOGIC (Reset state after successful execution) ---
                weight_restored = weight_original
                fail_count_reset = 0
                unblock_time_reset = 0.0
                
                # Requeue with restored values, maintaining its original high priority
                self.task_queue.append((
                    weight_restored, global_tier, local_level, logical_name, args, 
                    fail_count_reset, unblock_time_reset, weight_original
                ))
                
                self.task_queue.sort(key=lambda x: x[0])
            
            # Small sleep to yield CPU time, essential for monothread loops on low-spec hardware.
            time.sleep(0.001)

        logger.info("Kernel: Loop Finished.")