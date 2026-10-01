# ScheduRL

**Explore real-time scheduling and task offloading across IoT devices and edge servers.**

ScheduRL is a Python university project that simulates periodic and aperiodic workloads, compares local execution with learned offloading policies, and turns scheduling decisions into charts. It brings together earliest-deadline-first scheduling (EDF), an iTBS implementation, a genetic algorithm, and a small tabular Q-learning policy.

The repository includes two workflows: generated IoT-edge experiments for algorithm comparison, and scheduling tools for database tasks or JSON-defined workloads. All simulations run locally; no physical IoT hardware or cloud account is required.

## What you can explore

- **Offloading decisions:** compare local-only execution, GA-weighted decisions, and a Q-learning policy on the same generated workload.
- **System size and load:** vary device or server counts, then compare five load scales from `0.6` to `1.4`.
- **Scheduling mechanics:** inspect EDF ordering, iTBS bandwidth allocation, idle-time reclaim, and multiple edge servers.
- **Results:** inspect deadline success, latency, offloading ratio, makespan, and scheduling timelines.

## Getting started

Use **Python 3.10+**. Dependencies are pinned in [requirements.txt](requirements.txt): Pydantic, SQLAlchemy, and Matplotlib.

```bash
git clone https://github.com/Hemenam/SheduleRL.git
cd SheduleRL
python -m venv .venv
```

Activate the environment in your shell:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
source .venv/bin/activate
```

Then install dependencies and run a focused experiment:

```bash
python -m pip install -r requirements.txt
python main.py --mode staticserver --vars 20 --alg rl
```

This simulates **20 devices and 5 edge servers**, prints the selected policy's metrics, and creates a task table and scheduling chart in `plots/staticserver_vars20/`. Run commands from the repository root.

## Compare offloading policies

The experiment workflow first evaluates periodic tasks using EDF on each device, then simulates soft-task execution locally or on reachable edge servers.

| `--alg` | Policy | Decision method |
| --- | --- | --- |
| `none` | Local-only baseline | Execute every soft task on its device. |
| `gen` | Genetic algorithm | Evolve weights for a cost based on predicted finish time, energy, and deadline overrun; compare local execution with an edge candidate. |
| `rl` | Tabular Q-learning | Choose local or edge execution using discretized predicted timing advantage and deadline slack. |
| Omitted | Comparison | Run all three policies and generate comparison charts plus a load sweep. |

Both `--mode` and `--vars` are required for this workflow:

| Mode | Fixed entities | Meaning of `--vars` | Valid range |
| --- | --- | --- | --- |
| `staticserver` | 5 edge servers | Number of IoT devices | `10`–`50` |
| `iot` | 100 IoT devices | Number of edge servers | `1`–`20` |

```bash
# Compare all policies with 100 devices and 5 servers
python main.py --mode iot --vars 5

# Inspect the genetic policy with 30 devices and 5 servers
python main.py --mode staticserver --vars 30 --alg gen

# Inspect local-only execution with 100 devices and 3 servers
python main.py --mode iot --vars 3 --alg none
```

Experiments use a default random seed of `7`. The Python entry point, `run_iot_edge_experiment(...)` in [services/iot_edge_experiment.py](services/iot_edge_experiment.py), accepts a `seed` argument; the experiment CLI does not expose it.

### Generated files

Experiment outputs are saved under `plots/{mode}_vars{N}/`:

| File | Contents | Generated for |
| --- | --- | --- |
| `task_specification_table.csv` | Simulation parameters and periodic/soft task specifications | Every experiment |
| `7_scheduling_chart.png` | Offline EDF and online execution timelines | Every experiment |
| `1_offloading_ratio.png` | Local versus offloaded task percentages | Comparison |
| `2_hard_task_schedulability.png` | Percentage of devices passing the offline EDF check | Comparison |
| `3_soft_task_qos.png` | Average soft-task latency and deadline success | Comparison |
| `4_system_qos_vs_load.png` | Composite QoS score across five load scales | Comparison |
| `5_makespan.png` | Last soft-task completion time | Comparison |
| `6_soft_task_schedulability_rate.png` | Percentage of soft tasks meeting their deadlines | Comparison |
| `summary_metrics.txt` | Selected RL policy's metrics | Comparison |

In comparison mode, the printed summary and scheduling timeline select **RL**; the comparison charts include all three policies. The composite QoS score combines deadline success with inverse latency and inverse energy using weights of `0.50`, `0.35`, and `0.15`.

The scheduling chart shows a limited view: offline segments for device 0, and a subset of online records and resource lanes. Runs using the same mode and entity count reuse the output directory and overwrite matching filenames; files from an earlier comparison can remain after a focused run.

## Schedule stored tasks

The task CLI uses SQLite through SQLAlchemy and creates `tasks.db` in the repository root when needed.

```bash
python main.py seed
python main.py list

# Single-server iTBS with a Gantt chart
python main.py schedule --bandwidth 0.5 --plot gantt

# Two servers with different bandwidth allocations
python main.py schedule --bandwidths 0.4,0.6 --plot gantt --plot-file two_servers.png
```

Each server bandwidth must be in `(0, 1]`. Idle-time reclaim is enabled by default; add `--no-reclaim` to disable it. The default plot filename is `schedule_gantt.png`.

`seed` leaves a nonempty database unchanged. `seed --force` **appends** another set of sample tasks; it does not reset the database. To remove stored tasks, run `python main.py clear`.

## Run the online offloading scheduler

The `offload` subcommand is a separate scheduler workflow. It dispatches tasks at configurable simulation ticks and supports either a generated workload or a JSON input; the experiment policies above are selected through `--mode`, not this subcommand.

```bash
# Generate a reproducible workload with exactly 5 devices and 2 servers
python main.py offload --devices 5 --servers 2 --fixed-iot-count --fixed-server-count --random-seed 7

# Load the included workload example
python main.py offload --json data/offload_sample.json --plot-file sample_offload.png

# Inspect all available timing, workload, and bandwidth options
python main.py offload --help
```

Without the fixed-count flags, device and server counts are sampled between `1` and their respective limits. Generated workloads produce `offload_gantt.png` and an offline periodic schedule in `offload_gantt_offline.png`. JSON runs use the input's topology, tasks, transfer overhead, and reclaim setting; see [data/offload_sample.json](data/offload_sample.json) for an example.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite contains **19 unit tests** covering EDF ordering and validation, iTBS deadline assignment and reclaim behavior, multiple servers, local/offloaded execution, JSON loading, periodic-job expansion, generated workload bounds, tick-based dispatch, and task services/controllers backed by temporary databases.

These tests exercise scheduler and application behavior. They do not establish the GA/RL experiment's comparative performance or validate its modeling assumptions.

## Project layout

```text
SheduleRL/
├── main.py                    # Argument parsing and workflow entry points
├── controllers/               # Task, seed, scheduling, and command orchestration
├── models/                    # Database task model and IoT workload types
├── services/
│   ├── scheduler_service.py   # EDF, iTBS, and online offloading routines
│   ├── iot_edge_experiment.py # Generated workloads, GA/RL policies, metrics, plots
│   ├── iot_loader.py          # JSON loading and workload generation
│   └── task_service.py        # Database task operations
├── data/                      # Database setup, seed data, and a JSON example
├── views/                     # Console rendering and scheduler plots
├── tests/                     # Unit tests
├── requirements.txt
└── ScheduRL.pdf               # Project document
```

## Modeling scope

ScheduRL is an educational simulation with simplified timing, communication, and energy models. Interpret the charts as outputs of those assumptions, rather than evidence that one policy is generally superior.

- **Predicted and simulated local timing differ.** The experiment's decision features assume local slowdown from a fixed utilization proxy; recorded local execution uses the unscaled execution time. This can influence which policy appears preferable.
- **Periodic and soft execution are evaluated separately.** The offline EDF result is shared across policies; the experiment does not model a fully integrated schedule in which periodic and soft tasks contend for the same processor.
- **Policy training is simplified.** GA and Q-learning train on feature rows drawn from the same generated workload. There is no held-out evaluation or automatic aggregation across multiple seeds, and the Q-learning update uses the current state's values rather than a separately simulated next state.

Useful extensions include aligning predicted and executed timing, modeling shared periodic/soft-task contention, and adding independent workloads and multiple-seed evaluations before making performance claims.
