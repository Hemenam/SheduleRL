from __future__ import annotations

import csv
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
    link_rate_mbps: float


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


@dataclass(frozen=True)
class DecisionRecord:
    task_id: str
    device_id: int
    action: str
    server_id: int | None
    finish_time: float
    absolute_deadline: float
    met_deadline: bool
    latency: float
    energy: float


@dataclass(frozen=True)
class RunMetrics:
    algorithm: str
    offloading_ratio: float
    hard_schedulability_rate: float
    soft_deadline_success_rate: float
    avg_soft_latency: float
    makespan: float
    avg_energy_per_soft_task: float


def _distance(a_x: float, a_y: float, b_x: float, b_y: float) -> float:
    return math.hypot(a_x - b_x, a_y - b_y)


def _build_topology(mode: str, vars_n: int, rng: random.Random) -> tuple[list[DeviceNode], list[EdgeNode]]:
    if vars_n < 1:
        raise ValueError("--vars must be >= 1.")

    if mode == "staticserver":
        num_servers = 5
        num_devices = vars_n
    elif mode == "iot":
        num_devices = 100
        num_servers = vars_n
    else:
        raise ValueError("--mode must be one of: staticserver, iot")

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
            link_rate_mbps=rng.uniform(30.0, 80.0),
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
            nearest = min(
                servers,
                key=lambda s: _distance(device.x, device.y, s.x, s.y),
            )
            in_range = [nearest.server_id]
        connectivity[device.device_id] = in_range
    return connectivity


def _generate_periodic_tasks(
    devices: list[DeviceNode],
    load_scale: float,
    rng: random.Random,
) -> tuple[list[PeriodicTask], dict[int, float]]:
    tasks: list[PeriodicTask] = []
    utilization_by_device: dict[int, float] = {}
    for device in devices:
        weights = [rng.uniform(0.4, 1.6) for _ in range(20)]
        periods = [rng.uniform(18.0, 80.0) for _ in range(20)]
        util_target = min(0.92, 0.52 + (0.22 * load_scale) + rng.uniform(-0.05, 0.05))
        weight_sum = sum(weights)
        device_util = 0.0

        for idx, (weight, period) in enumerate(zip(weights, periods)):
            util_i = util_target * (weight / weight_sum)
            execution = max(0.03, util_i * period)
            device_util += execution / period
            tasks.append(
                PeriodicTask(
                    task_id=f"p{device.device_id}_{idx}",
                    device_id=device.device_id,
                    period=period,
                    execution_time=execution,
                    release_offset=rng.uniform(0.0, period * 0.1),
                )
            )

        utilization_by_device[device.device_id] = device_util
    return tasks, utilization_by_device


def _offline_schedulability(utilization_by_device: dict[int, float]) -> float:
    schedulable = sum(1 for util in utilization_by_device.values() if util <= 1.0)
    if not utilization_by_device:
        return 0.0
    return schedulable / len(utilization_by_device)


def _generate_soft_tasks(
    devices: list[DeviceNode],
    load_scale: float,
    rng: random.Random,
) -> list[SoftTask]:
    tasks: list[SoftTask] = []
    base_count = max(2, int(round(4 * load_scale)))
    for device in devices:
        count = base_count + rng.randint(0, max(2, int(2 * load_scale)))
        for idx in range(count):
            execution = rng.uniform(0.15, 1.4)
            relative_deadline = rng.uniform(2.0, 7.5)
            tasks.append(
                SoftTask(
                    task_id=f"a{device.device_id}_{idx}",
                    device_id=device.device_id,
                    arrival_time=rng.uniform(0.0, 120.0),
                    execution_time=execution,
                    relative_deadline=relative_deadline,
                    data_size_mb=rng.uniform(0.2, 3.0),
                )
            )
    tasks.sort(key=lambda t: (t.arrival_time, t.task_id))
    return tasks


def _predict_offload(
    task: SoftTask,
    device: DeviceNode,
    server: EdgeNode,
    server_finish: float,
) -> tuple[float, float, float]:
    d = _distance(device.x, device.y, server.x, server.y)
    one_way_latency = (task.data_size_mb * 8.0 / server.link_rate_mbps) + (d * 0.0007)
    network_latency = 2.0 * one_way_latency
    remote_execution = task.execution_time / server.compute_factor
    start_time = max(task.arrival_time + network_latency, server_finish)
    finish_time = start_time + remote_execution
    energy = 1.25 * network_latency
    return finish_time, network_latency, energy


def _build_decision_features(
    task: SoftTask,
    device: DeviceNode,
    local_finish: float,
    periodic_util: float,
    reachable_servers: list[EdgeNode],
    server_finish_times: dict[int, float],
) -> dict[str, float]:
    local_speed_penalty = 1.0 / max(0.05, 1.0 - periodic_util)
    predicted_local_finish = max(task.arrival_time, local_finish) + (
        task.execution_time * local_speed_penalty
    )
    deadline_abs = task.arrival_time + task.relative_deadline

    best_server_id = -1
    best_finish = float("inf")
    best_net_latency = 0.0
    best_energy = 0.0

    for server in reachable_servers:
        off_finish, net_latency, off_energy = _predict_offload(
            task=task,
            device=device,
            server=server,
            server_finish=server_finish_times[server.server_id],
        )
        if off_finish < best_finish:
            best_finish = off_finish
            best_server_id = server.server_id
            best_net_latency = net_latency
            best_energy = off_energy

    local_energy = 0.35 * task.execution_time
    return {
        "deadline_abs": deadline_abs,
        "local_finish": predicted_local_finish,
        "local_energy": local_energy,
        "off_finish": best_finish,
        "off_energy": best_energy,
        "best_server_id": float(best_server_id),
        "network_latency": best_net_latency,
    }


def _train_ga_weights(
    feature_rows: list[dict[str, float]],
    rng: random.Random,
) -> tuple[float, float, float]:
    population = [
        [rng.uniform(0.6, 1.6), rng.uniform(0.05, 0.5), rng.uniform(1.0, 3.0)]
        for _ in range(18)
    ]

    def fitness(chromosome: list[float]) -> float:
        w_latency, w_energy, w_miss = chromosome
        score = 0.0
        for row in feature_rows:
            d = row["deadline_abs"]
            local_penalty = max(0.0, row["local_finish"] - d)
            off_penalty = max(0.0, row["off_finish"] - d)
            local_score = (w_latency * row["local_finish"]) + (w_energy * row["local_energy"]) + (
                w_miss * local_penalty
            )
            off_score = (w_latency * row["off_finish"]) + (w_energy * row["off_energy"]) + (
                w_miss * off_penalty
            )
            score += min(local_score, off_score)
        return -score

    for _ in range(24):
        ranked = sorted(population, key=fitness, reverse=True)
        next_gen = ranked[:6]
        while len(next_gen) < len(population):
            a, b = rng.sample(ranked[:10], 2)
            child = [
                (a[0] + b[0]) / 2.0,
                (a[1] + b[1]) / 2.0,
                (a[2] + b[2]) / 2.0,
            ]
            idx = rng.randint(0, 2)
            child[idx] *= rng.uniform(0.85, 1.15)
            child[idx] = max(0.01, child[idx])
            next_gen.append(child)
        population = next_gen

    return tuple(sorted(population, key=fitness, reverse=True)[0])  # type: ignore[return-value]


def _discretize_state(local_finish: float, off_finish: float, deadline_abs: float) -> tuple[int, int]:
    gain = off_finish - local_finish
    slack = deadline_abs - min(local_finish, off_finish)

    if gain < -2.0:
        g_bin = 0
    elif gain < -0.5:
        g_bin = 1
    elif gain < 0.5:
        g_bin = 2
    elif gain < 2.0:
        g_bin = 3
    else:
        g_bin = 4

    if slack < 0.0:
        s_bin = 0
    elif slack < 1.0:
        s_bin = 1
    elif slack < 3.0:
        s_bin = 2
    else:
        s_bin = 3
    return g_bin, s_bin


def _train_rl_qtable(
    feature_rows: list[dict[str, float]],
    rng: random.Random,
) -> dict[tuple[int, int], list[float]]:
    q_table: dict[tuple[int, int], list[float]] = {}
    alpha = 0.25
    gamma = 0.92
    epsilon = 0.25

    for _ in range(18):
        for row in feature_rows:
            state = _discretize_state(row["local_finish"], row["off_finish"], row["deadline_abs"])
            q = q_table.setdefault(state, [0.0, 0.0])
            if rng.random() < epsilon:
                action = rng.randint(0, 1)
            else:
                action = 0 if q[0] >= q[1] else 1

            if action == 0:
                finish = row["local_finish"]
                energy = row["local_energy"]
            else:
                finish = row["off_finish"]
                energy = row["off_energy"]
            miss = 1.0 if finish > row["deadline_abs"] else 0.0
            reward = -(finish + (3.0 * miss) + (0.25 * energy))
            q[action] = q[action] + alpha * (reward + (gamma * max(q)) - q[action])
        epsilon = max(0.05, epsilon * 0.9)

    return q_table


def _simulate(
    algorithm: str,
    devices: list[DeviceNode],
    servers: list[EdgeNode],
    connectivity: dict[int, list[int]],
    periodic_util: dict[int, float],
    soft_tasks: list[SoftTask],
    rng: random.Random,
) -> tuple[RunMetrics, list[DecisionRecord]]:
    local_finish_times: dict[int, float] = {d.device_id: 0.0 for d in devices}
    local_virtual_deadline: dict[int, float] = {d.device_id: 0.0 for d in devices}
    server_finish_times: dict[int, float] = {s.server_id: 0.0 for s in servers}
    server_virtual_deadline: dict[int, float] = {s.server_id: 0.0 for s in servers}
    u_local_soft = 0.35
    u_server_soft = 0.65

    device_by_id = {d.device_id: d for d in devices}
    server_by_id = {s.server_id: s for s in servers}

    sampled_features: list[dict[str, float]] = []
    for task in soft_tasks[: min(500, len(soft_tasks))]:
        device = device_by_id[task.device_id]
        reachable = [server_by_id[sid] for sid in connectivity[task.device_id]]
        sampled_features.append(
            _build_decision_features(
                task=task,
                device=device,
                local_finish=local_finish_times[task.device_id],
                periodic_util=periodic_util[task.device_id],
                reachable_servers=reachable,
                server_finish_times=server_finish_times,
            )
        )

    ga_weights = (1.0, 0.2, 2.0)
    q_table: dict[tuple[int, int], list[float]] = {}
    if algorithm == "gen":
        ga_weights = _train_ga_weights(sampled_features, rng)
    elif algorithm == "rl":
        q_table = _train_rl_qtable(sampled_features, rng)

    records: list[DecisionRecord] = []

    for task in soft_tasks:
        device = device_by_id[task.device_id]
        reachable = [server_by_id[sid] for sid in connectivity[task.device_id]]
        features = _build_decision_features(
            task=task,
            device=device,
            local_finish=local_finish_times[task.device_id],
            periodic_util=periodic_util[task.device_id],
            reachable_servers=reachable,
            server_finish_times=server_finish_times,
        )
        deadline_abs = features["deadline_abs"]

        offload = False
        if algorithm == "none":
            offload = False
        elif algorithm == "gen":
            w_l, w_e, w_m = ga_weights
            local_pen = max(0.0, features["local_finish"] - deadline_abs)
            off_pen = max(0.0, features["off_finish"] - deadline_abs)
            local_score = (w_l * features["local_finish"]) + (w_e * features["local_energy"]) + (
                w_m * local_pen
            )
            off_score = (w_l * features["off_finish"]) + (w_e * features["off_energy"]) + (
                w_m * off_pen
            )
            offload = off_score < local_score
        else:
            state = _discretize_state(features["local_finish"], features["off_finish"], deadline_abs)
            q_vals = q_table.get(state, [0.0, 0.0])
            offload = q_vals[1] > q_vals[0]

        if offload:
            server_id = int(features["best_server_id"])
            server = server_by_id[server_id]
            predicted_finish, network_latency, off_energy = _predict_offload(
                task=task,
                device=device,
                server=server,
                server_finish=server_finish_times[server_id],
            )
            arrival_edge = task.arrival_time + network_latency
            vd = max(arrival_edge, server_virtual_deadline[server_id])
            assigned_deadline = vd + ((task.execution_time / server.compute_factor) / u_server_soft)
            server_virtual_deadline[server_id] = assigned_deadline
            server_finish_times[server_id] = predicted_finish
            finish = predicted_finish
            energy = off_energy
            action = "offload"
            used_server = server_id
        else:
            util = periodic_util[task.device_id]
            slowdown = 1.0 / max(0.05, 1.0 - util)
            start = max(task.arrival_time, local_finish_times[task.device_id])
            finish = start + (task.execution_time * slowdown)
            vd = max(task.arrival_time, local_virtual_deadline[task.device_id])
            assigned_deadline = vd + ((task.execution_time * slowdown) / u_local_soft)
            local_virtual_deadline[task.device_id] = assigned_deadline
            local_finish_times[task.device_id] = finish
            energy = 0.35 * task.execution_time
            action = "local"
            used_server = None

        records.append(
            DecisionRecord(
                task_id=task.task_id,
                device_id=task.device_id,
                action=action,
                server_id=used_server,
                finish_time=finish,
                absolute_deadline=deadline_abs,
                met_deadline=finish <= deadline_abs,
                latency=max(0.0, finish - task.arrival_time),
                energy=energy,
            )
        )

    offloaded_count = sum(1 for r in records if r.action == "offload")
    met_soft_count = sum(1 for r in records if r.met_deadline)
    makespan = max((r.finish_time for r in records), default=0.0)
    avg_latency = sum(r.latency for r in records) / max(1, len(records))
    avg_energy = sum(r.energy for r in records) / max(1, len(records))

    metrics = RunMetrics(
        algorithm=algorithm,
        offloading_ratio=offloaded_count / max(1, len(records)),
        hard_schedulability_rate=_offline_schedulability(periodic_util),
        soft_deadline_success_rate=met_soft_count / max(1, len(records)),
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
    periodic_tasks_per_device: int,
    soft_tasks_total: int,
) -> Path:
    output_path = output_dir / "task_specification_table.csv"
    rows = [
        ["parameter", "value"],
        ["mode", mode],
        ["vars", vars_n],
        ["periodic_tasks_per_device", periodic_tasks_per_device],
        ["total_soft_tasks", soft_tasks_total],
        ["communication_range", range_limit],
        ["itbs_formula", "d_i = max(r_i, d_(i-1)) + C_i / U_s"],
    ]
    with output_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerows(rows)
    return output_path


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

    def _save(fig, filename: str) -> None:
        path = output_dir / filename
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        output_paths.append(path)

    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.bar(labels, [m.offloading_ratio * 100.0 for m in metrics_by_alg], color=["#577590", "#43aa8b", "#f8961e"])
    ax1.set_ylabel("Offloaded Tasks (%)")
    ax1.set_title("Offloading Ratio Chart")
    _save(fig1, "1_offloading_ratio.png")

    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.bar(labels, [m.hard_schedulability_rate * 100.0 for m in metrics_by_alg], color=["#4d908e", "#277da1", "#90be6d"])
    ax2.set_ylabel("Schedulable Devices (%)")
    ax2.set_title("Hard Task Schedulability")
    _save(fig2, "2_hard_task_schedulability.png")

    fig3, ax3 = plt.subplots(figsize=(8, 4))
    x = list(range(len(labels)))
    latencies = [m.avg_soft_latency for m in metrics_by_alg]
    deadline_success = [m.soft_deadline_success_rate * 100.0 for m in metrics_by_alg]
    ax3.bar([idx - 0.2 for idx in x], latencies, width=0.4, label="Avg Latency (s)", color="#277da1")
    ax3_t = ax3.twinx()
    ax3_t.bar([idx + 0.2 for idx in x], deadline_success, width=0.4, label="Deadline Success (%)", color="#f3722c")
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels)
    ax3.set_title("Soft Task QoS")
    ax3.set_ylabel("Latency (s)")
    ax3_t.set_ylabel("Deadline Success (%)")
    _save(fig3, "3_soft_task_qos.png")

    fig4, ax4 = plt.subplots(figsize=(8, 4))
    for alg, points in qos_vs_load.items():
        points_sorted = sorted(points, key=lambda pair: pair[0])
        ax4.plot(
            [p[0] for p in points_sorted],
            [p[1] * 100.0 for p in points_sorted],
            marker="o",
            label=alg.upper(),
        )
    ax4.set_xlabel("Load Scale")
    ax4.set_ylabel("Soft Deadline Success (%)")
    ax4.set_title("System QoS vs. Load")
    ax4.legend()
    _save(fig4, "4_system_qos_vs_load.png")

    fig5, ax5 = plt.subplots(figsize=(8, 4))
    ax5.bar(labels, [m.makespan for m in metrics_by_alg], color=["#577590", "#f9c74f", "#43aa8b"])
    ax5.set_ylabel("Makespan (s)")
    ax5.set_title("Makespan Chart")
    _save(fig5, "5_makespan.png")

    fig6, ax6 = plt.subplots(figsize=(8, 4))
    ax6.bar(labels, [m.soft_deadline_success_rate * 100.0 for m in metrics_by_alg], color=["#577590", "#43aa8b", "#f94144"])
    ax6.set_ylabel("Aperiodic Deadline Met (%)")
    ax6.set_title("Soft Task Schedulability Rate")
    _save(fig6, "6_soft_task_schedulability_rate.png")

    summary_path = output_dir / "summary_metrics.txt"
    summary_path.write_text(
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
    output_paths.append(summary_path)
    return output_paths


def run_iot_edge_experiment(mode: str, vars_n: int, alg: str, seed: int = 7) -> dict[str, object]:
    if alg not in {"none", "gen", "rl"}:
        raise ValueError("--alg must be one of: none, gen, rl")

    rng = random.Random(seed)
    devices, servers = _build_topology(mode=mode, vars_n=vars_n, rng=rng)
    range_limit = 35.0
    connectivity = _build_connectivity(devices=devices, servers=servers, range_limit=range_limit)

    base_periodic, base_periodic_util = _generate_periodic_tasks(
        devices=devices,
        load_scale=1.0,
        rng=rng,
    )
    base_soft = _generate_soft_tasks(devices=devices, load_scale=1.0, rng=rng)

    none_metrics, _ = _simulate(
        algorithm="none",
        devices=devices,
        servers=servers,
        connectivity=connectivity,
        periodic_util=base_periodic_util,
        soft_tasks=base_soft,
        rng=random.Random(seed + 11),
    )
    gen_metrics, _ = _simulate(
        algorithm="gen",
        devices=devices,
        servers=servers,
        connectivity=connectivity,
        periodic_util=base_periodic_util,
        soft_tasks=base_soft,
        rng=random.Random(seed + 13),
    )
    rl_metrics, records = _simulate(
        algorithm="rl",
        devices=devices,
        servers=servers,
        connectivity=connectivity,
        periodic_util=base_periodic_util,
        soft_tasks=base_soft,
        rng=random.Random(seed + 17),
    )

    selected_map = {"none": none_metrics, "gen": gen_metrics, "rl": rl_metrics}
    selected_metrics = selected_map[alg]

    qos_vs_load: dict[str, list[tuple[float, float]]] = {"none": [], "gen": [], "rl": []}
    for scale in [0.6, 0.8, 1.0, 1.2, 1.4]:
        _, periodic_util = _generate_periodic_tasks(devices=devices, load_scale=scale, rng=rng)
        soft_tasks = _generate_soft_tasks(devices=devices, load_scale=scale, rng=rng)
        for name in ("none", "gen", "rl"):
            metrics, _ = _simulate(
                algorithm=name,
                devices=devices,
                servers=servers,
                connectivity=connectivity,
                periodic_util=periodic_util,
                soft_tasks=soft_tasks,
                rng=random.Random(seed + int(scale * 100) + (0 if name == "none" else 7 if name == "gen" else 14)),
            )
            qos_vs_load[name].append((scale, metrics.soft_deadline_success_rate))

    output_dir = Path("plots").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    task_table = _save_task_spec_table(
        output_dir=output_dir,
        mode=mode,
        vars_n=vars_n,
        range_limit=range_limit,
        periodic_tasks_per_device=20,
        soft_tasks_total=len(base_soft),
    )
    chart_paths = _save_charts(
        output_dir=output_dir,
        selected=selected_metrics,
        baseline_none=none_metrics,
        baseline_gen=gen_metrics,
        proposed_rl=rl_metrics,
        qos_vs_load=qos_vs_load,
    )

    offloaded = sum(1 for row in records if row.action == "offload")
    return {
        "mode": mode,
        "vars": vars_n,
        "alg": alg,
        "devices": len(devices),
        "servers": len(servers),
        "periodic_tasks": len(base_periodic),
        "soft_tasks": len(base_soft),
        "selected_metrics": selected_metrics,
        "offloaded_tasks_by_rl": offloaded,
        "generated_files": [str(p) for p in [task_table, *chart_paths]],
    }
