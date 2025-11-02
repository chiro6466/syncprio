
from .decorators import system, engine, runner, lpt
from .kernel import PriorityKernel

# Snippet for AI/VS Code (English)
"""
Usage Snippet:
from syncprio import PriorityKernel, system, engine

# 1. Define a system initialization task (Phase 1, runs once, strict sequence)
@system(seq=10, key="DB_CONNECT")
def initialize_database():
    print("Connecting to DB...")

# 2. Define a continuous loop task (Phase 2, high priority)
@engine(prio=5, key="DATA_POLLER")
def run_data_polling():
    # This runs continuously in the monothread loop
    pass

# 3. Main execution flow
if __name__ == '__main__':
    kernel = PriorityKernel()
    
    # Add tasks by function reference (Standard Mode) or key (Darkness Mode)
    kernel.add_task(initialize_database)
    kernel.add_task(run_data_polling)
    
    # Run the system
    kernel.run_system_tasks(["DB_CONNECT"]) # Run Phase 1
    kernel.run_loop() # Run Phase 2
"""

__all__ = [
    'system',
    'engine',
    'runner',
    'lpt',
    'PriorityKernel',
]