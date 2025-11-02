import logging
import random
import time
from typing import Dict, Any, List, Tuple, Callable
from venv import logger

# NOTE: The actual 'syncprio' library components must be accessible here.
# For this demo, we assume the files are in the same directory structure.
# We will use MOCKS for demonstration purposes.

# --- MOCK LIBRARY IMPORTS ---
# In a real environment, you would use: from syncprio import PriorityKernel, engine, runner
# We mock the necessary components and constants for a self-contained test.

# MOCK ROLE MAP (Used in the real kernel)
ROLE_PRIORITY_MAP = {
    'SYSTEM': 0, 
    'ENGINE': 1, 
    'RUNNER': 2, 
    'LPT': 3     
}

# MOCK MAX FAILS (Simplified for quick testing)
ROLE_MAX_FAILS = {
    'ENGINE': 3, # Critical task fails 3 times, then discards.
    'RUNNER': 2, # Standard task fails 2 times, then discards.
    'LPT': 1     
}

# MOCK TASK DECORATORS (Simplified to only inject metadata)
def _inject_metadata(obj, key, role, global_tier, local_level):
    setattr(obj, '_kernel_role', role)
    setattr(obj, '_global_priority_tier', global_tier)
    setattr(obj, '_local_sequence_level', local_level)
    setattr(obj, '_logical_name', key)
    return obj

def engine(prio: int, key: str) -> Callable:
    def actual_decorator(obj: Any):
        return _inject_metadata(obj, key, 'ENGINE', ROLE_PRIORITY_MAP['ENGINE'], prio)
    return actual_decorator

def runner(prio: int, key: str) -> Callable:
    def actual_decorator(obj: Any):
        return _inject_metadata(obj, key, 'RUNNER', ROLE_PRIORITY_MAP['RUNNER'], prio)
    return actual_decorator

# MOCK KERNEL CLASS (Simulates the relevant methods for testing)
class MockPriorityKernel:
    # --- TASK DEFINITION (Snippet for IA/User) ---
    # Task = (weight, global_tier, local_level, logical_name, args, fail_count, unblock_time, weight_original)
    Task = Tuple[int, int, int, str, Dict[str, Any], int, float, int]

    # --- RESILIENCE CONSTANTS (Must match kernel.py) ---
    MAX_PENALTY_WEIGHT = 399
    BASE_BACKOFF_TIME = 0.5
    MAX_DELAY_CAP = 5.0 

    def __init__(self):
        self.task_queue: List[self.Task] = []
        self.is_running = True
        self.execution_count = 0 # Global counter for the forced failure logic

    def _calculate_weight(self, global_tier: int, local_level: int) -> int:
        return (global_tier * 100) + local_level

    def add_task(self, task_reference: Callable, args: Dict[str, Any] = None):
        """Adds a task, initializing resilience state (fail_count=0, unblock_time=0.0)."""
        args = args or {}
        task_obj = task_reference
        
        # Metadata retrieval (simplified)
        role = getattr(task_obj, '_kernel_role')
        global_tier = getattr(task_obj, '_global_priority_tier')
        local_level = getattr(task_obj, '_local_sequence_level')
        logical_name = getattr(task_obj, '_logical_name')
        
        weight = self._calculate_weight(global_tier, local_level)

        # Initialize Resilience State
        new_task: self.Task = (
            weight, global_tier, local_level, logical_name, args,
            0, # fail_count (Initial: 0)
            0.0, # unblock_time (Initial: 0.0)
            weight # weight_original 
        )
        self.task_queue.append(new_task)
        self.task_queue.sort(key=lambda x: x[0])
        logger.info(f"SETUP: Task '{logical_name}' ({role}) added. Initial Weight: {weight}")

    # --- MAIN TEST LOOP (Simulates kernel.run_loop()) ---
    def run_test_loop(self, duration_s: int):
        """Runs the simulation for a fixed duration to observe Jitter and discard."""
        start_test_time = time.time()
        
        logger.info(f"\n--- STARTING STRESS TEST: Duration {duration_s}s ---")
        
        while (time.time() - start_test_time) < duration_s:
            if not self.task_queue:
                time.sleep(0.01)
                continue
            
            # Extract and Unpack 8 elements
            (weight, global_tier, local_level, logical_name, args, 
             fail_count, unblock_time, weight_original) = self.task_queue.pop(0)
            
            role = next(k for k, v in ROLE_PRIORITY_MAP.items() if v == global_tier)

            # --- 1. JITTER/BACKOFF DELAY CHECK ---
            if unblock_time > time.time():
                # Task is in backoff. Requeue immediately and skip execution.
                logger.debug(f" [DELAY] -> Role: {role}, Name: {logical_name} waiting backoff ({unblock_time - time.time():.2f}s left).")
                
                # Requeue with same state (Weight is already penalized)
                self.task_queue.append((
                    weight, global_tier, local_level, logical_name, args, 
                    fail_count, unblock_time, weight_original
                ))
                self.task_queue.sort(key=lambda x: x[0])
                time.sleep(0.001) # Yield CPU
                continue
            
            # --- 2. EXECUTION (FORCED FAILURE) ---
            try:
                task_func = globals()[logical_name] 
                
                # Critical logging to see the attempt number
                logger.info(f" [EXEC] -> Role: {role}, Name: {logical_name}. Attempt #{fail_count + 1}/{ROLE_MAX_FAILS.get(role)}")
                
                task_func(self) # Pass self to access the global counter for the mock failure
                
            except Exception as e:
                # --- 3. TASK CRASH & RESILIENCE PENALTY LOGIC ---
                
                max_fails = ROLE_MAX_FAILS.get(role, 1)
                fail_count += 1
                
                if fail_count >= max_fails:
                    # Policy: Discard task permanently
                    logger.critical(f" [FATAL DISCARD] 🚨 Role: {role}, Name: {logical_name} failed {fail_count} times. PERMANENTLY DISCARDED.")
                    continue 

                # Exponential Backoff Calculation
                exponential_delay = self.BASE_BACKOFF_TIME * (2 ** fail_count)
                
                # Jitter: Random delay, capped by MAX_DELAY_CAP
                delay = min(random.uniform(0, exponential_delay), self.MAX_DELAY_CAP)
                unblock_time = time.time() + delay
                
                # Penalty: Degrade priority to MAX_PENALTY_WEIGHT
                weight_new = self.MAX_PENALTY_WEIGHT 
                
                logger.error(f" [FAIL PENALTY] -> Role: {role}, Name: {logical_name} failed. Requeuing with {delay:.2f}s Jitter (New Weight: {weight_new}).")
                
                # Requeue with the new penalized state
                self.task_queue.append((
                    weight_new, global_tier, local_level, logical_name, args, 
                    fail_count, unblock_time, weight_original
                ))
                self.task_queue.sort(key=lambda x: x[0])
                continue

            # --- 4. SUCCESS: RESTORATION LOGIC ---
            if role in ['ENGINE', 'RUNNER', 'LPT']:
                # Reset state after successful execution
                weight_restored = weight_original
                fail_count_reset = 0
                unblock_time_reset = 0.0
                
                # Requeue with original values
                self.task_queue.append((
                    weight_restored, global_tier, local_level, logical_name, args, 
                    fail_count_reset, unblock_time_reset, weight_original
                ))
                self.task_queue.sort(key=lambda x: x[0])
        
        logger.info("\n--- TEST FINISHED: Simulation Time Ended ---")

# --- MOCK TASKS WITH FORCED FAILURE LOGIC ---

# Tarea de Alta Prioridad (ENGINE)
@engine(prio=10, key="API_AUTH")
def API_AUTH(kernel_instance: MockPriorityKernel):
    """Simulates a critical authentication task that fails frequently."""
    kernel_instance.execution_count += 1
    if kernel_instance.execution_count <= 4:
        # Force failure for the first 4 total executions (Engine will fail twice, Runner twice)
        raise ConnectionError("API connection error simulated.")
    # Success after 4 attempts
    logger.info(" [TASK SUCCESS] -> API_AUTH succeeded, resetting backoff state.")

# Tarea de Media Prioridad (RUNNER)
@runner(prio=50, key="BUSINESS_LOGIC")
def BUSINESS_LOGIC(kernel_instance: MockPriorityKernel):
    """Simulates a standard business logic task with lower failure tolerance."""
    if kernel_instance.execution_count <= 2:
        # Fails the first 2 times the kernel executes it.
        raise TimeoutError("Business logic failed due to timeout.")
    
    # This task will be discarded before succeeding because its max_fails is 2.
    # The logic above ensures it should be discarded on the 3rd attempt check.
    pass


# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # 1. SETUP LOGGING for noisy output (ver paso a paso)
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    kernel_logger = logging.getLogger('syncprio')
    logger.setLevel(logging.DEBUG) 
    
    # 2. INITIALIZE AND ADD TASKS
    kernel = MockPriorityKernel()
    kernel.add_task(API_AUTH)       # ENGINE (Priority 110)
    kernel.add_task(BUSINESS_LOGIC) # RUNNER (Priority 250)
    
    logger.info("\n--- INITIAL QUEUE: API_AUTH (High) runs before BUSINESS_LOGIC (Medium) ---")

    # 3. RUN TEST
    # Run for 10 seconds to observe backoff and re-execution patterns.
    kernel.run_test_loop(duration_s=10)