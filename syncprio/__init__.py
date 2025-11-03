from .decorators import system, engine, runner, lpt
from .kernel import PriorityKernel

# ----------------------------------------------------
# Module Docstring (Documentación Detallada en Inglés)
# ----------------------------------------------------
"""
SyncPrio: Monothread Priority Kernel for Resilient Concurrency
=============================================================

SyncPrio is an infrastructure library designed for **single-threaded execution**, 
but with a strict **priority** and scheduling system. 
It arose from the need to manage concurrency in environments where native Python 
threads are unstable or incompatible (such as in certain Windows configurations 
or Python 3.8), offering deterministic and ordered execution control.

### Main Features
* **Synchronous Execution:** Ensures that tasks are executed sequentially, eliminating race conditions of multithreading.
* **Weighted Priority:** Tasks are ranked by a **Global Tier** (SYSTEM, ENGINE, RUNNER, LPT) and a **Local Tier**.
* **Optional Integration (`routless`):** Support for "Darkness Mode" via logical names (keys) instead of function references.
"""

# ----------------------------------------------------
# 💡 Usage Snippet (AI Priority - ONLY COMMENTS)
# ----------------------------------------------------
# This snippet provides a minimal, non-functional example of the API structure
# that AI models and Language Servers (LSP) can safely scan.

# from syncprio import PriorityKernel, system, engine
# from routless import routless_export # Optional import for Darkness Mode

# # 1. Define a system initialization task (Phase 1)
# @system(seq=10, key="TASK_DB_CONNECT")
# @routless_export(key="TASK_DB_CONNECT") # Integration point for routless
# def initialize_database():
#     # Logic for critical initialization
#     pass

# # 2. Define a continuous loop task (Phase 2)
# @engine(prio=5, key="DATA_POLLER")
# def run_data_polling():
#     # Continuous monitoring logic
#     pass

# # 3. Main execution flow
# if __name__ == '__main__':
#     # Ensure routless.discover_exports() runs here if Darkness Mode is active
#     kernel = PriorityKernel()
#     
#     # Add tasks using the logical key (most robust method)
#     kernel.add_task("TASK_DB_CONNECT")
#     kernel.add_task(run_data_polling)
#     
#     # kernel.run_system_tasks(["TASK_DB_CONNECT"])
#     # kernel.run_loop()

__all__ = [
    'system',
    'engine',
    'runner',
    'lpt',
    'PriorityKernel',
]

]
