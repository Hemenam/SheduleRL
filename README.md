# ScheduRL

ScheduRL is a command-line real-time scheduling sandbox focused on aperiodic workload management with iTBS (Improved Total Bandwidth Server).

It provides:
- SQLite persistence for task/workload data.
- ORM-based data access with SQLAlchemy.
- CLI commands for seeding, listing, clearing, and scheduling.
- IoT offloading simulation with device-local execution or edge server scheduling.
- Optional Gantt chart rendering for schedule visualization.

## 1. Project Purpose

This project is designed for experimenting with real-time scheduling behavior using an aperiodic task model.

Core goals:
- Model aperiodic workloads with release times, execution budgets, and deadlines.
- Run iTBS assignment and inspect generated service intervals/deadlines.
- Visualize execution timelines with a generated Gantt plot.

## 2. Tech Stack

- Python 3.14
- SQLite (database file at project root: `tasks.db`)
- SQLAlchemy 2.x (ORM)
- Matplotlib (optional plotting)

## 3. Installation

### 3.1 Clone / Open Project

```bash
cd /path/to/ScheduRL
```

### 3.2 Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### 3.3 Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Running the CLI

All commands are run through `main.py`:

```bash
python main.py <command> [options]
```

If no command is provided, default behavior is equivalent to `list`.

## 5. Commands Reference

### 5.1 `seed`

Populate database with advanced aperiodic seed workload.

```bash
python main.py seed
```

Behavior:
- If DB already has tasks, seed is skipped.

Force replace existing data:

```bash
python main.py seed --force
```

Behavior with `--force`:
- Clears all existing rows.
- Inserts the full advanced seed set.

### 5.2 `list`

Show all tasks in release-time order:

```bash
python main.py list
```

Output fields:
- `r`: release time
- `C`: WCET / execution time
- `D`: relative deadline
- `T`: period (`-` for aperiodic dataset)

### 5.3 `clear`

Delete all tasks from the database:

```bash
python main.py clear
```

### 5.4 `schedule`

Run a scheduler on current tasks.

Current supported algorithm:
- `itbs`

Basic usage:

```bash
python main.py schedule -a itbs
```

Options:
- `-u`, `--bandwidth`: single iTBS server bandwidth `U_s` in `(0, 1]`.
- `--bandwidths`: comma-separated iTBS server bandwidths for multi-server mode (example: `0.4,0.6`).
- `--no-reclaim`: disable idle-time reclaim behavior.
- `--plot gantt`: generate Gantt chart.
- `--plot-file <path>`: output image path.

Examples:

```bash
python main.py schedule -a itbs -u 0.55
python main.py schedule -a itbs --bandwidths 0.35,0.45,0.20
python main.py schedule -a itbs --no-reclaim
python main.py schedule -a itbs --plot gantt --plot-file plots/itbs_gantt.png
```

### 5.5 `offload`

Schedule IoT tasks with online offloading to edge servers.

Rules:
- There are `n` tasks and `n` IoT devices.
- Each task is initially assigned to exactly one device.
- If a task arrives when its device is idle, it executes locally on that device.
- If the device is busy, the task is offloaded to one of `k` servers.
- Offloaded tasks incur a constant transfer overhead `t`.

Examples:

```bash
python main.py offload -u 0.55 -k 3 -t 0.2
python main.py offload --bandwidths 0.35,0.45,0.20 -t 0.1
python main.py offload -u 0.55 -k 2 -t 0.2 --plot gantt --plot-file plots/offload_gantt.png
```

## 6. Data Model

ORM entity: `RealTimeTask` (`models/task.py`)

Columns:
- `id` (PK)
- `name`
- `task_type` (default: `aperiodic`)
- `release_time`
- `wcet`
- `relative_deadline`
- `period` (nullable)
- `description` (nullable)

Note: current workflow treats all seeded tasks as aperiodic.

Additional in-memory models for the offloading simulation (`models/iot.py`):
- `IoTDevice` (device_id)
- `EdgeServer` (server_id, bandwidth)
- `IoTTask` (task_id, name, release_time, execution_time, assigned_device_id)

## 7. Architecture Overview

The code is split by responsibility.

### 7.1 `controllers/`

Command orchestration layer.

- `command_controller.py`
  - Thin command router/dispatcher.
- `task_controller.py`
  - Handles `list`, `clear` logic.
- `seed_controller.py`
  - Handles seed workflow.
- `schedule_controller.py`
  - Handles iTBS scheduling workflow.
- `seed_data.py`
  - Advanced seed dataset definition.

### 7.2 `services/`

Business logic and persistence operations.

- `task_service.py`
  - CRUD-style DB operations via SQLAlchemy sessions.
- `scheduler_service.py`
  - iTBS algorithm implementation (`schedule_itbs`).

### 7.3 `views/`

Rendering/output layer only.

- `task_view.py`: task list and empty-state output.
- `seed_view.py`: seed status messages.
- `clear_view.py`: clear status messages.
- `schedule_view.py`: schedule text rendering + Gantt image generation.

### 7.4 `data/`

Database setup and ORM base.

- `database.py`
  - engine/session factory
  - metadata initialization (`init_db()`)

## 8. iTBS Summary

Implemented rule:

Single server:
`d_i = max(r_i, d_(i-1)) + C_i / U_s`

Multi-server:
- Each server keeps its own virtual deadline timeline.
- Each incoming job is assigned to the earliest-available server.
- Deadline assignment then uses that server's bandwidth.

Where:
- `r_i` = arrival/release time
- `C_i` = execution time
- `U_s` = server bandwidth
- `d_i` = assigned deadline

Optional behavior:
- Idle-time reclaim can be disabled with `--no-reclaim`.

## 9. IoT Offloading Summary

Each task is assigned to a unique IoT device. At arrival time:
- If the device is idle, the task runs locally.
- If the device is busy, the task is offloaded to one of the edge servers.
- Offloading adds a constant transfer overhead `t` to the service time.
- Servers use iTBS to assign deadlines and schedule service.

## 10. Typical Workflow

```bash
python main.py clear
python main.py seed
python main.py list
python main.py schedule -a itbs -u 0.55 --plot gantt --plot-file plots/run1.png
```

## 11. Output Files

- Database: `tasks.db` (project root)
- Plot files: user-defined via `--plot-file` (default: `schedule_gantt.png`)

## 12. Troubleshooting

### 12.1 No tasks found

Run:

```bash
python main.py seed
```

### 12.2 Replace old data with fresh seed

Run:

```bash
python main.py seed --force
```

### 11.3 Plot not generated where expected

Use an explicit path and check output message:

```bash
python main.py schedule -a itbs --plot gantt --plot-file plots/check.png
```

The CLI prints the absolute path of the saved image.

## 12. Future Extension Ideas

- Add more scheduling algorithms (e.g., CBS variants, EDF baseline traces).
- Add import/export for workload profiles.
- Add response-time and deadline-miss statistics report command.
- Add tests for controller flows and scheduler edge cases.
