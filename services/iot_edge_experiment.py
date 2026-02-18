from __future__ import annotations

import csv
import heapq
import math
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeviceNode:
    device_id: int
    x: float
    y: float


@dataclass(frozen=True)
class EdgeNode:
    server_id: int
    x: float
    y: float
    compute_factor: float
    uplink_mbps: float
    downlink_mbps: float


@dataclass(frozen=True)
class PeriodicTask:
    task_id: str
    device_id: int
    period: float
    execution_time: float
    release_offset: float


@dataclass(frozen=True)
class SoftTask:
    task_id: str
    device_id: int
    arrival_time: float
    execution_time: float
    relative_deadline: float
    data_size_mb: float
    result_size_mb: float


@dataclass(frozen=True)
class DecisionRecord:
    task_id: str
    device_id: int
    action: str
    server_id: int | None
    start_time: float
    finish_time: float
    absolute_deadline: float
    met_deadline: bool
    latency: float
    energy: float
    resource_label: str


@dataclass(frozen=True)
class RunMetrics:
    algorithm: str
    offloading_ratio: float
    hard_schedulability_rate: float
    soft_deadline_success_rate: float
    avg_soft_latency: float
    makespan: float
    avg_energy_per_soft_task: float


@dataclass(frozen=True)
class Segment:
    start: float
    finish: float
    label: str


def _distance(a_x: float, a_y: float, b_x: float, b_y: float) -> float:
    return math.hypot(a_x - b_x, a_y - b_y)


def _validate_range(mode: str, vars_n: int) -> None:
    if mode == "staticserver":
        if vars_n < 10 or vars_n > 50:
            raise ValueError("For --mode staticserver, --vars must be in [10, 50].")
    elif mode == "iot":
        if vars_n < 1 or vars_n > 20:
            raise ValueError("For --mode iot, --vars must be in [1, 20].")
    else:
        raise ValueError("--mode must be one of: staticserver, iot")


def _build_topology(mode: str, vars_n: int, rng: random.Random) -> tuple[list[DeviceNode], list[EdgeNode]]:
    _validate_range(mode, vars_n)

    if mode == "staticserver":
        num_servers = 5
        num_devices = vars_n
    else:
        num_devices = 100
        num_servers = vars_n

    devices = [
        DeviceNode(
            device_id=i,
            x=rng.uniform(0.0, 100.0),
            y=rng.uniform(0.0, 100.0),
        )
        for i in range(num_devices)
    ]
    servers = [
        EdgeNode(
            server_id=i,
            x=rng.uniform(0.0, 100.0),
            y=rng.uniform(0.0, 100.0),
            compute_factor=rng.uniform(1.8, 2.8),
            uplink_mbps=rng.uniform(30.0, 75.0),
            downlink_mbps=rng.uniform(35.0, 85.0),
        )
        for i in range(num_servers)
    ]
    return devices, servers


def _build_connectivity(
    devices: list[DeviceNode],
    servers: list[EdgeNode],
    range_limit: float,
) -> dict[int, list[int]]:
    connectivity: dict[int, list[int]] = {}
    for device in devices:
        in_range = [
            server.server_id
            for server in servers
            if _distance(device.x, device.y, server.x, server.y) <= range_limit
        ]
        if not in_range:
            nearest = min(servers, key=lambda s: _distance(device.x, device.y, s.x, s.y))
            in_range = [nearest.server_id]
        connectivity[device.device_id] = in_range
    return connectivity


def _generate_periodic_tasks(devices: list[DeviceNode], rng: random.Random, load_scale: float) -> list[PeriodicTask]:
    tasks: list[PeriodicTask] = []
    for device in devices:
        util_target = min(0.95, 0.64 + (0.18 * load_scale))
        weights = [rng.uniform(0.5, 1.6) for _ in range(20)]
        periods = [rng.choice([20.0, 25.0, 40.0, 50.0, 100.0]) for _ in range(20)]
        weight_sum = sum(weights)

        for idx, (w, period) in enumerate(zip(weights, periods)):
            util_i = util_target * (w / weight_sum)
            execution = max(0.02, util_i * period)
            tasks.append(
                PeriodicTask(
                    task_id=f"p{device.device_id}_{idx}",
                    device_id=device.device_id,
                    period=period,
                    execution_time=execution,
                    release_offset=rng.uniform(0.0, period * 0.05),
                )
            )
    return tasks


def _edf_schedulability_for_device(tasks: list[PeriodicTask], horizon: float) -> tuple[bool, list[Segment]]:
    releases: list[tuple[float, int]] = []
    for idx, task in enumerate(tasks):
        t = task.release_offset
        while t <= horizon + 1e-9:
            releases.append((t, idx))
            t += task.period
    releases.sort(key=lambda x: x[0])

    ready: list[tuple[float, int, float, str]] = []
    segments: list[Segment] = []
    miss = False
    now = 0.0
    release_cursor = 0

    while release_cursor < len(releases) or ready:
        while release_cursor < len(releases) and releases[release_cursor][0] <= now + 1e-9:
            release_t, idx = releases[release_cursor]
            task = tasks[idx]
            deadline = release_t + task.period
            heapq.heappush(ready, (deadline, idx, task.execution_time, task.task_id))
            release_cursor += 1

        if not ready:
            now = releases[release_cursor][0]
            continue

        deadline, idx, remaining, task_id = heapq.heappop(ready)
        if now > deadline + 1e-9:
            miss = True
            break

        next_release = releases[release_cursor][0] if release_cursor < len(releases) else float("inf")
        run = min(remaining, next_release - now)
        if run <= 1e-9:
            run = remaining

        start = now
        finish = now + run
        if finish - start > 1e-9:
            segments.append(Segment(start=start, finish=finish, label=task_id))

        now = finish
        remaining_after = remaining - run
        if remaining_after > 1e-9:
            heapq.heappush(ready, (deadline, idx, remaining_after, task_id))
        elif now > deadline + 1e-9:
            miss = True
            break

    return (not miss), segments


def _offline_phase(
    periodic_tasks: list[PeriodicTask], device_count: int, horizon: float = 200.0
) -> tuple[float, list[Segment]]:
    by_device: dict[int, list[PeriodicTask]] = {idx: [] for idx in range(device_count)}
    for task in periodic_tasks:
        by_device[task.device_id].append(task)

    schedulable = 0
    sample_segments: list[Segment] = []
    for device_id in range(device_count):
        ok, segments = _edf_schedulability_for_device(by_device[device_id], horizon)
        if ok:
            schedulable += 1
        if device_id == 0:
            sample_segments = segments[:200]
    return schedulable / max(1, device_count), sample_segments


def _generate_soft_tasks(devices: list[DeviceNode], rng: random.Random, load_scale: float) -> list[SoftTask]:
    tasks: list[SoftTask] = []
    base = max(2, int(round(4.0 * load_scale)))
    for device in devices:
        count = base + rng.randint(0, max(2, int(2 * load_scale)))
        for idx in range(count):
            payload = rng.uniform(0.3, 3.0)
            tasks.append(
                SoftTask(
                    task_id=f"a{device.device_id}_{idx}",
                    device_id=device.device_id,
                    arrival_time=rng.uniform(0.0, 120.0),
                    execution_time=rng.uniform(0.12, 1.5),
                    relative_deadline=rng.uniform(2.2, 8.0),
                    data_size_mb=payload,
                    result_size_mb=max(0.06, payload * rng.uniform(0.2, 0.5)),
                )
            )
    tasks.sort(key=lambda t: (t.arrival_time, t.task_id))
    return tasks


def _predict_offload(
    task: SoftTask, device: DeviceNode, server: EdgeNode, server_finish: float
) -> tuple[float, float, float, float]:
    d = _distance(device.x, device.y, server.x, server.y)
    propagation = d * 0.00065
    uplink = (task.data_size_mb * 8.0 / server.uplink_mbps) + propagation
    downlink = (task.result_size_mb * 8.0 / server.downlink_mbps) + propagation
    total_network = uplink + downlink
    remote_execution = task.execution_time / server.compute_factor
    start_time = max(task.arrival_time + uplink, server_finish)
    finish_time = start_time + remote_execution + downlink
    energy = (1.10 * uplink) + (0.90 * downlink)
    return start_time, finish_time, total_network, energy


def _build_features(
    task: SoftTask,
    device: DeviceNode,
    local_finish_prev: float,
    local_util: float,
    reachable_servers: list[EdgeNode],
    server_finish_times: dict[int, float],
) -> dict[str, float]:
    slowdown = 1.0 / max(0.1, 1.0 - min(0.95, local_util))
    local_start = max(task.arrival_time, local_finish_prev)
    local_finish = local_start + (task.execution_time * slowdown)
    abs_deadline = task.arrival_time + task.relative_deadline

    best_server_id = -1
    best_start = 0.0
    best_finish = float("inf")
    best_energy = 0.0
    best_network = 0.0

    for server in reachable_servers:
        off_start, off_finish, off_network, off_energy = _predict_offload(
            task=task, device=device, server=server, server_finish=server_finish_times[server.server_id]
        )
        if off_finish < best_finish:
            best_server_id = server.server_id
            best_start = off_start
            best_finish = off_finish
            best_energy = off_energy
            best_network = off_network

    return {
        "deadline": abs_deadline,
        "local_start": local_start,
        "local_finish": local_finish,
        "local_energy": 0.33 * task.execution_time,
        "off_start": best_start,
        "off_finish": best_finish,
        "off_energy": best_energy,
        "off_network": best_network,
        "best_server_id": float(best_server_id),
    }


def _train_ga_weights(rows: list[dict[str, float]], rng: random.Random) -> tuple[float, float, float]:
    population = [[rng.uniform(0.7, 1.8), rng.uniform(0.05, 0.5), rng.uniform(1.2, 3.5)] for _ in range(20)]

    def fitness(chrom: list[float]) -> float:
        w_t, w_e, w_m = chrom
        score = 0.0
        for row in rows:
            d = row["deadline"]
            local_miss = max(0.0, row["local_finish"] - d)
            off_miss = max(0.0, row["off_finish"] - d)
            local_cost = (w_t * row["local_finish"]) + (w_e * row["local_energy"]) + (w_m * local_miss)
            off_cost = (w_t * row["off_finish"]) + (w_e * row["off_energy"]) + (w_m * off_miss)
            score += min(local_cost, off_cost)
        return -score

    for _ in range(25):
        ranked = sorted(population, key=fitness, reverse=True)
        next_gen = ranked[:6]
        while len(next_gen) < len(population):
            a, b = rng.sample(ranked[:12], 2)
            child = [(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0]
            k = rng.randint(0, 2)
            child[k] = max(0.01, child[k] * rng.uniform(0.85, 1.15))
            next_gen.append(child)
        population = next_gen

    best = sorted(population, key=fitness, reverse=True)[0]
    return best[0], best[1], best[2]


def _rl_state(local_finish: float, off_finish: float, deadline: float) -> tuple[int, int]:
    gain = off_finish - local_finish
    slack = deadline - min(local_finish, off_finish)
    g_bin = 0 if gain < -1.5 else 1 if gain < -0.3 else 2 if gain < 0.5 else 3
    s_bin = 0 if slack < 0.0 else 1 if slack < 1.2 else 2 if slack < 3.0 else 3
    return g_bin, s_bin


def _train_q_table(rows: list[dict[str, float]], rng: random.Random) -> dict[tuple[int, int], list[float]]:
    q: dict[tuple[int, int], list[float]] = {}
    alpha = 0.22
    gamma = 0.90
    epsilon = 0.28

    for _ in range(20):
        for row in rows:
            state = _rl_state(row["local_finish"], row["off_finish"], row["deadline"])
            q_vals = q.setdefault(state, [0.0, 0.0])
            action = rng.randint(0, 1) if rng.random() < epsilon else (0 if q_vals[0] >= q_vals[1] else 1)

            if action == 0:
                finish = row["local_finish"]
                energy = row["local_energy"]
            else:
                finish = row["off_finish"]
                energy = row["off_energy"]
            miss = 1.0 if finish > row["deadline"] else 0.0
            reward = -(finish + (3.0 * miss) + (0.25 * energy))
            q_vals[action] = q_vals[action] + alpha * (reward + gamma * max(q_vals) - q_vals[action])
        epsilon = max(0.05, epsilon * 0.9)
    return q


def _simulate(
    algorithm: str,
    devices: list[DeviceNode],
    servers: list[EdgeNode],
    connectivity: dict[int, list[int]],
    offline_sched_rate: float,
    soft_tasks: list[SoftTask],
    rng: random.Random,
) -> tuple[RunMetrics, list[DecisionRecord]]:
    local_finish: dict[int, float] = {d.device_id: 0.0 for d in devices}
    local_vd: dict[int, float] = {d.device_id: 0.0 for d in devices}
    server_finish: dict[int, float] = {s.server_id: 0.0 for s in servers}
    server_vd: dict[int, float] = {s.server_id: 0.0 for s in servers}
    u_local_soft = 0.35
    u_server_soft = 0.65

    device_by_id = {d.device_id: d for d in devices}
    server_by_id = {s.server_id: s for s in servers}

    feature_rows: list[dict[str, float]] = []
    for task in soft_tasks[: min(800, len(soft_tasks))]:
        device = device_by_id[task.device_id]
        reachable = [server_by_id[sid] for sid in connectivity[task.device_id]]
        util_proxy = 0.75
        feature_rows.append(
            _build_features(
                task=task,
                device=device,
                local_finish_prev=local_finish[task.device_id],
                local_util=util_proxy,
                reachable_servers=reachable,
                server_finish_times=server_finish,
            )
        )

    ga = (1.0, 0.2, 2.0)
    q_table: dict[tuple[int, int], list[float]] = {}
    if algorithm == "gen":
        ga = _train_ga_weights(feature_rows, rng)
    elif algorithm == "rl":
        q_table = _train_q_table(feature_rows, rng)

    records: list[DecisionRecord] = []
    for task in soft_tasks:
        device = device_by_id[task.device_id]
        reachable = [server_by_id[sid] for sid in connectivity[task.device_id]]
        util_proxy = 0.75
        row = _build_features(
            task=task,
            device=device,
            local_finish_prev=local_finish[task.device_id],
            local_util=util_proxy,
            reachable_servers=reachable,
            server_finish_times=server_finish,
        )
        deadline = row["deadline"]

        do_offload = False
        if algorithm == "gen":
            w_t, w_e, w_m = ga
            local_miss = max(0.0, row["local_finish"] - deadline)
            off_miss = max(0.0, row["off_finish"] - deadline)
            local_cost = (w_t * row["local_finish"]) + (w_e * row["local_energy"]) + (w_m * local_miss)
            off_cost = (w_t * row["off_finish"]) + (w_e * row["off_energy"]) + (w_m * off_miss)
            do_offload = off_cost < local_cost
        elif algorithm == "rl":
            state = _rl_state(row["local_finish"], row["off_finish"], deadline)
            q_vals = q_table.get(state, [0.0, 0.0])
            do_offload = q_vals[1] > q_vals[0]

        if do_offload:
            sid = int(row["best_server_id"])
            server = server_by_id[sid]
            off_start, off_finish, _, off_energy = _predict_offload(
                task=task, device=device, server=server, server_finish=server_finish[sid]
            )
            vd = max(off_start, server_vd[sid])
            assigned_deadline = vd + ((task.execution_time / server.compute_factor) / u_server_soft)
            server_vd[sid] = assigned_deadline
            server_finish[sid] = off_finish
            start_time = off_start
            finish_time = off_finish
            energy = off_energy
            action = "offload"
            server_id = sid
            resource = f"S{sid}"
        else:
            start_time = max(task.arrival_time, local_finish[task.device_id])
            finish_time = start_time + task.execution_time
            vd = max(start_time, local_vd[task.device_id])
            assigned_deadline = vd + (task.execution_time / u_local_soft)
            local_vd[task.device_id] = assigned_deadline
            local_finish[task.device_id] = finish_time
            energy = 0.33 * task.execution_time
            action = "local"
            server_id = None
            resource = f"D{task.device_id}"

        records.append(
            DecisionRecord(
                task_id=task.task_id,
                device_id=task.device_id,
                action=action,
                server_id=server_id,
                start_time=start_time,
                finish_time=finish_time,
                absolute_deadline=deadline,
                met_deadline=finish_time <= deadline,
                latency=max(0.0, finish_time - task.arrival_time),
                energy=energy,
                resource_label=resource,
            )
        )

    offloaded = sum(1 for r in records if r.action == "offload")
    met = sum(1 for r in records if r.met_deadline)
    makespan = max((r.finish_time for r in records), default=0.0)
    avg_latency = sum(r.latency for r in records) / max(1, len(records))
    avg_energy = sum(r.energy for r in records) / max(1, len(records))

    metrics = RunMetrics(
        algorithm=algorithm,
        offloading_ratio=offloaded / max(1, len(records)),
        hard_schedulability_rate=offline_sched_rate,
        soft_deadline_success_rate=met / max(1, len(records)),
        avg_soft_latency=avg_latency,
        makespan=makespan,
        avg_energy_per_soft_task=avg_energy,
    )
    return metrics, records


def _save_task_spec_table(
    output_dir: Path,
    mode: str,
    vars_n: int,
    range_limit: float,
    periodic_tasks: list[PeriodicTask],
    soft_tasks: list[SoftTask],
) -> Path:
    path = output_dir / "task_specification_table.csv"
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["parameter", "value"])
        writer.writerow(["mode", mode])
        writer.writerow(["vars", vars_n])
        writer.writerow(["communication_range", range_limit])
        writer.writerow(["periodic_tasks_per_device", 20])
        writer.writerow(["itbs_formula", "d_i = max(r_i, d_(i-1)) + C_i/U_s"])
        writer.writerow([])
        writer.writerow(["task_type", "task_id", "device_id", "release_or_arrival", "execution", "period_or_deadline", "data_mb", "result_mb"])
        for task in periodic_tasks:
            writer.writerow(
                [
                    "periodic",
                    task.task_id,
                    task.device_id,
                    f"{task.release_offset:.4f}",
                    f"{task.execution_time:.4f}",
                    f"{task.period:.4f}",
                    "-",
                    "-",
                ]
            )
        for task in soft_tasks:
            writer.writerow(
                [
                    "soft",
                    task.task_id,
                    task.device_id,
                    f"{task.arrival_time:.4f}",
                    f"{task.execution_time:.4f}",
                    f"{task.relative_deadline:.4f}",
                    f"{task.data_size_mb:.4f}",
                    f"{task.result_size_mb:.4f}",
                ]
            )
    return path


def _save_scheduling_chart(
    output_dir: Path, offline_segments: list[Segment], selected_records: list[DecisionRecord], selected_alg: str
) -> Path:
    import matplotlib.pyplot as plt

    path = output_dir / "7_scheduling_chart.png"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=False)

    for seg in offline_segments[:140]:
        ax1.broken_barh([(seg.start, seg.finish - seg.start)], (10, 8), facecolors="#577590", edgecolors="#1d3557")
    ax1.set_yticks([14])
    ax1.set_yticklabels(["Device0-EDF"])
    ax1.set_title("Offline EDF Scheduling Chart")
    ax1.grid(axis="x", linestyle="--", alpha=0.35)

    shown = sorted(selected_records, key=lambda r: (r.start_time, r.task_id))[:220]
    lanes: dict[str, int] = {}
    for rec in shown:
        if rec.resource_label not in lanes and len(lanes) < 9:
            lanes[rec.resource_label] = len(lanes)
    for rec in shown:
        lane = lanes.get(rec.resource_label)
        if lane is None:
            continue
        y = lane * 10
        color = "#43aa8b" if rec.action == "local" else "#f8961e"
        ax2.broken_barh([(rec.start_time, rec.finish_time - rec.start_time)], (y, 8), facecolors=color, edgecolors="#264653")

    ax2.set_yticks([i * 10 + 4 for i in range(len(lanes))])
    ax2.set_yticklabels(list(lanes.keys()))
    ax2.set_title(f"Online Scheduling Chart ({selected_alg.upper()})")
    ax2.grid(axis="x", linestyle="--", alpha=0.35)
    ax2.set_xlabel("Time (s)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _save_charts(
    output_dir: Path,
    selected: RunMetrics,
    baseline_none: RunMetrics,
    baseline_gen: RunMetrics,
    proposed_rl: RunMetrics,
    qos_vs_load: dict[str, list[tuple[float, float]]],
) -> list[Path]:
    import matplotlib.pyplot as plt

    output_paths: list[Path] = []
    metrics_by_alg = [baseline_none, baseline_gen, proposed_rl]
    labels = [m.algorithm.upper() for m in metrics_by_alg]

    def _save(fig, name: str) -> None:
        p = output_dir / name
        fig.tight_layout()
        fig.savefig(p, dpi=150)
        plt.close(fig)
        output_paths.append(p)

    fig1, ax1 = plt.subplots(figsize=(8, 4))
    off = [m.offloading_ratio * 100.0 for m in metrics_by_alg]
    local = [100.0 - x for x in off]
    ax1.bar(labels, off, label="Offloaded", color="#f8961e")
    ax1.bar(labels, local, bottom=off, label="Local", color="#577590")
    ax1.set_ylabel("Soft Tasks (%)")
    ax1.set_title("Ratio of Offloaded vs Non-Offloaded Soft Tasks")
    ax1.legend()
    _save(fig1, "1_offloading_ratio.png")

    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.bar(labels, [m.hard_schedulability_rate * 100.0 for m in metrics_by_alg], color=["#4d908e", "#277da1", "#90be6d"])
    ax2.set_ylabel("Schedulable Devices (%)")
    ax2.set_title("Hard Task Schedulability Chart")
    _save(fig2, "2_hard_task_schedulability.png")

    fig3, ax3 = plt.subplots(figsize=(8, 4))
    x = list(range(len(labels)))
    ax3.bar([i - 0.2 for i in x], [m.avg_soft_latency for m in metrics_by_alg], width=0.4, label="Latency (s)", color="#277da1")
    ax3_t = ax3.twinx()
    ax3_t.bar([i + 0.2 for i in x], [m.soft_deadline_success_rate * 100.0 for m in metrics_by_alg], width=0.4, label="Success (%)", color="#f3722c")
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels)
    ax3.set_title("Service Quality (QoS) Chart")
    ax3.set_ylabel("Latency (s)")
    ax3_t.set_ylabel("Success (%)")
    _save(fig3, "3_soft_task_qos.png")

    fig4, ax4 = plt.subplots(figsize=(8, 4))
    for alg, points in qos_vs_load.items():
        s = sorted(points, key=lambda pair: pair[0])
        ax4.plot([p[0] for p in s], [p[1] * 100.0 for p in s], marker="o", label=alg.upper())
    ax4.set_xlabel("System Load Scale")
    ax4.set_ylabel("Soft Task Success (%)")
    ax4.set_title("System QoS in Various States")
    ax4.legend()
    _save(fig4, "4_system_qos_vs_load.png")

    fig5, ax5 = plt.subplots(figsize=(8, 4))
    ax5.bar(labels, [m.makespan for m in metrics_by_alg], color=["#577590", "#f9c74f", "#43aa8b"])
    ax5.set_ylabel("Total Completion Time (s)")
    ax5.set_title("Makespan Chart")
    _save(fig5, "5_makespan.png")

    fig6, ax6 = plt.subplots(figsize=(8, 4))
    ax6.bar(labels, [m.soft_deadline_success_rate * 100.0 for m in metrics_by_alg], color=["#577590", "#43aa8b", "#f94144"])
    ax6.set_ylabel("Deadline Met (%)")
    ax6.set_title("Soft Task Schedulability Rate")
    _save(fig6, "6_soft_task_schedulability_rate.png")

    summary = output_dir / "summary_metrics.txt"
    summary.write_text(
        "\n".join(
            [
                f"selected_algorithm={selected.algorithm}",
                f"selected_offloading_ratio={selected.offloading_ratio:.4f}",
                f"selected_soft_success={selected.soft_deadline_success_rate:.4f}",
                f"selected_avg_latency={selected.avg_soft_latency:.4f}",
                f"selected_makespan={selected.makespan:.4f}",
            ]
        ),
        encoding="utf-8",
    )
    output_paths.append(summary)
    return output_paths


def run_iot_edge_experiment(mode: str, vars_n: int, alg: str, seed: int = 7) -> dict[str, object]:
    if alg not in {"none", "gen", "rl"}:
        raise ValueError("--alg must be one of: none, gen, rl")

    rng = random.Random(seed)
    devices, servers = _build_topology(mode=mode, vars_n=vars_n, rng=rng)
    range_limit = 35.0
    connectivity = _build_connectivity(devices=devices, servers=servers, range_limit=range_limit)

    periodic_tasks = _generate_periodic_tasks(devices=devices, rng=rng, load_scale=1.0)
    hard_sched_rate, offline_segments = _offline_phase(periodic_tasks, device_count=len(devices))
    soft_tasks = _generate_soft_tasks(devices=devices, rng=rng, load_scale=1.0)

    run_none, rec_none = _simulate(
        algorithm="none",
        devices=devices,
        servers=servers,
        connectivity=connectivity,
        offline_sched_rate=hard_sched_rate,
        soft_tasks=soft_tasks,
        rng=random.Random(seed + 11),
    )
    run_gen, rec_gen = _simulate(
        algorithm="gen",
        devices=devices,
        servers=servers,
        connectivity=connectivity,
        offline_sched_rate=hard_sched_rate,
        soft_tasks=soft_tasks,
        rng=random.Random(seed + 13),
    )
    run_rl, rec_rl = _simulate(
        algorithm="rl",
        devices=devices,
        servers=servers,
        connectivity=connectivity,
        offline_sched_rate=hard_sched_rate,
        soft_tasks=soft_tasks,
        rng=random.Random(seed + 17),
    )

    metrics_map = {"none": run_none, "gen": run_gen, "rl": run_rl}
    records_map = {"none": rec_none, "gen": rec_gen, "rl": rec_rl}
    selected_metrics = metrics_map[alg]
    selected_records = records_map[alg]

    qos_vs_load: dict[str, list[tuple[float, float]]] = {"none": [], "gen": [], "rl": []}
    for scale in [0.6, 0.8, 1.0, 1.2, 1.4]:
        periodic = _generate_periodic_tasks(devices=devices, rng=rng, load_scale=scale)
        hard_rate, _ = _offline_phase(periodic, device_count=len(devices))
        soft = _generate_soft_tasks(devices=devices, rng=rng, load_scale=scale)
        for name in ("none", "gen", "rl"):
            m, _ = _simulate(
                algorithm=name,
                devices=devices,
                servers=servers,
                connectivity=connectivity,
                offline_sched_rate=hard_rate,
                soft_tasks=soft,
                rng=random.Random(seed + int(scale * 100) + (0 if name == "none" else 7 if name == "gen" else 14)),
            )
            qos_vs_load[name].append((scale, m.soft_deadline_success_rate))

    output_dir = (Path("plots") / f"{mode}_vars{vars_n}").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    table_path = _save_task_spec_table(
        output_dir=output_dir,
        mode=mode,
        vars_n=vars_n,
        range_limit=range_limit,
        periodic_tasks=periodic_tasks,
        soft_tasks=soft_tasks,
    )
    chart_paths = _save_charts(
        output_dir=output_dir,
        selected=selected_metrics,
        baseline_none=run_none,
        baseline_gen=run_gen,
        proposed_rl=run_rl,
        qos_vs_load=qos_vs_load,
    )
    sched_chart = _save_scheduling_chart(
        output_dir=output_dir,
        offline_segments=offline_segments,
        selected_records=selected_records,
        selected_alg=alg,
    )

    return {
        "mode": mode,
        "vars": vars_n,
        "alg": alg,
        "devices": len(devices),
        "servers": len(servers),
        "periodic_tasks": len(periodic_tasks),
        "soft_tasks": len(soft_tasks),
        "selected_metrics": selected_metrics,
        "generated_files": [str(p) for p in [table_path, *chart_paths, sched_chart]],
        "output_dir": str(output_dir),
    }
