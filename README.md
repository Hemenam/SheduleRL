========================================================================
ScheduRL: IoT-Edge Task Offloading & RL Scheduling Framework
========================================================================

ScheduRL is a research-oriented sandbox for simulating real-time task
scheduling in IoT-Edge environments. It compares traditional baselines
against Genetic Algorithms (GA) and Reinforcement Learning (Q-Learning)
to optimize task offloading and deadline success rates.

---

1. CORE CAPABILITIES

---

- Hybrid Workloads: Supports both Periodic (hard real-time) and
  Soft (aperiodic) tasks.
- Offline/Online Phases: Uses EDF for local periodic tasks and
  intelligent offloading for dynamic soft-task arrivals.
- Multi-Algorithm Support:
  - NONE: Local-only execution (Baseline).
  - GEN: Genetic Algorithm-based offloading optimization.
  - RL: Q-Learning agent that learns offloading policies.
- Scalability Testing: Automated modes to stress-test by varying
  the number of IoT devices or Edge Servers.

---

2. INSTALLATION

---

# 1. Clone the repository

cd ScheduRL

# 2. Setup virtual environment

python -m venv venv
source venv/bin/activate # Windows: venv\Scripts\activate

# 3. Install dependencies

pip install -r requirements.txt

---

3. EXPERIMENT MODES

---

The framework operates in two primary experimental modes:

A. Static Server Mode (--mode staticserver)

- Fixed: 5 Edge Servers.
- Variable (--vars N): N number of IoT devices.
- Goal: Test system performance under high device density.

B. IoT Fleet Mode (--mode iot)

- Fixed: 100 IoT Devices.
- Variable (--vars N): N number of Edge Servers.
- Goal: Test infrastructure scalability.

---

4. USAGE EXAMPLES

---

# RUN A FULL COMPARISON (Benchmark Mode)

# Runs None, GA, and RL algorithms across multiple load scales (0.6 to 1.4).

# Generates comprehensive comparison charts in the /plots folder.

python main.py --mode iot --vars 5

# RUN A SPECIFIC ALGORITHM (Focused Mode)

# Runs ONLY the specified algorithm.

# Generates a detailed Scheduling Gantt chart and Task Specification table.

python main.py --mode staticserver --vars 20 --alg rl

# LIST CURRENT DATABASE TASKS

python main.py list

# RESET ENVIRONMENT

python main.py clear
python main.py seed --force

---

5. OUTPUTS & VISUALIZATION

---

All results are stored in the `/plots/{mode}_vars{N}/` directory:

- task_spec_table.csv: Technical specifications of all generated tasks.
- scheduling*gantt*{alg}.png: A visual timeline of task execution.
- comparison_charts.png: (Comparison mode only) Graphs for:
  - Soft Deadline Success Rate
  - Average Latency
  - Success Rate vs. System Load
  - Makespan / Resource Utilization

---

6. PROJECT STRUCTURE

---

/controllers : CLI Command handling logic.
/models : Data structures for IoT Devices, Servers, and Tasks.
/services : Core simulation engine and RL/GA implementations.
/views : Plotting and CLI output formatting.
main.py : The primary entry point for the framework.
========================================================================
