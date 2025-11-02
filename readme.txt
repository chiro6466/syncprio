# 🚀 SyncPrio: Priority-Based Synchronous Execution Kernel

SyncPrio is an infrastructure library designed for **single-threaded execution**, but with a strict **priority** and *scheduling* system.

It arose from the need to manage concurrency in environments where native Python threads are unstable or incompatible (such as in certain Windows configurations or Python 3.8), offering deterministic and ordered execution control.

### 🌟 Main Features

* **Synchronous Execution:** Ensures that tasks are executed sequentially, eliminating the *race conditions* of multithreading.

* **Weighted Priority:** Tasks are ranked by a **Global Tier** (SYSTEM, ENGINE, RUNNER, LPT) and a **Local Tier**, ensuring that critical tasks are always executed first.

* **Optional Integration (`routless`):** Support for "Darkness Mode," which allows tasks to be loaded using logical names (tokens) without exposing their physical path.

### 📦 Installation

```bash
pip install syncprio