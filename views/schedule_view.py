from pathlib import Path

from services import ITBSJob, TaskService, schedule_itbs


def _render_gantt_plot(
    results,
    task_name_by_id: dict[str, str],
    output_path: str,
    algorithm: str,
    bandwidth: float,
) -> None:
    import matplotlib.pyplot as plt

    fig_height = max(4, len(results) * 0.55)
    fig, ax = plt.subplots(figsize=(12, fig_height))

    y_ticks = []
    y_labels = []

    for i, row in enumerate(results):
        y = i * 10
        duration = row.service_finish_time - row.service_start_time
        label = f"[{row.job_id}] {task_name_by_id[row.job_id]}"

        ax.broken_barh(
            [(row.service_start_time, duration)],
            (y, 7),
            facecolors="#2A9D8F",
            edgecolors="#264653",
            linewidth=1.0,
        )
        ax.scatter(row.arrival_time, y + 3.5, color="#E76F51", s=18, zorder=3)
        ax.scatter(row.assigned_deadline, y + 3.5, color="#1D3557", s=18, zorder=3)

        y_ticks.append(y + 3.5)
        y_labels.append(label)

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_xlabel("Time")
    ax.set_ylabel("Aperiodic Jobs")
    ax.set_title(f"{algorithm.upper()} Schedule Gantt (U_s={bandwidth:.3f})")
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.margins(x=0.02)

    plt.tight_layout()
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def schedule_view(
    task_service: TaskService,
    algorithm: str,
    bandwidth: float = 0.5,
    reclaim_idle_time: bool = True,
    plot: str | None = None,
    plot_file: str = "schedule_gantt.png",
) -> int:
    tasks = task_service.list_tasks()
    if not tasks:
        print("No aperiodic tasks found. Run `python main.py seed` first.")
        return 0

    if algorithm != "itbs":
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    jobs: list[ITBSJob] = []
    task_name_by_id: dict[str, str] = {}

    for task in tasks:
        execution_time = float(task.wcet)
        if execution_time <= 0.0:
            raise ValueError(
                f"Task {task.id} ('{task.name}') has invalid wcet: must be > 0."
            )

        task_id = str(task.id)
        task_name_by_id[task_id] = task.name
        jobs.append(
            ITBSJob(
                job_id=task_id,
                arrival_time=float(task.release_time),
                execution_time=execution_time,
            )
        )

    results = schedule_itbs(
        jobs=jobs,
        server_bandwidth=bandwidth,
        reclaim_idle_time=reclaim_idle_time,
    )

    print(f"Schedule algorithm: {algorithm.upper()} (U_s={bandwidth:.3f})")
    for row in results:
        name = task_name_by_id[row.job_id]
        print(
            f"[{row.job_id}] {name} | "
            f"r={row.arrival_time:.2f}, C={row.execution_time:.2f}, "
            f"d={row.assigned_deadline:.2f}, "
            f"svc=[{row.service_start_time:.2f}, {row.service_finish_time:.2f}]"
        )

    if plot is not None:
        if plot != "gantt":
            raise ValueError(f"Unsupported plot type: {plot}")
        output = _render_gantt_plot(
            results=results,
            task_name_by_id=task_name_by_id,
            output_path=plot_file,
            algorithm=algorithm,
            bandwidth=bandwidth,
        )
        print(f"Gantt plot saved to: {output}")

    return len(results)
