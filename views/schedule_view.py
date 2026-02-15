from pathlib import Path


def render_schedule(results, task_name_by_id: dict[str, str], algorithm: str, bandwidth: float) -> None:
    print(f"Schedule algorithm: {algorithm.upper()} (U_s={bandwidth:.3f})")
    for row in results:
        name = task_name_by_id[row.job_id]
        print(
            f"[{row.job_id}] {name} | "
            f"r={row.arrival_time:.2f}, C={row.execution_time:.2f}, "
            f"d={row.assigned_deadline:.2f}, "
            f"svc=[{row.service_start_time:.2f}, {row.service_finish_time:.2f}]"
        )


def save_gantt_plot(
    results,
    task_name_by_id: dict[str, str],
    output_path: str,
    algorithm: str,
    bandwidth: float,
) -> Path:
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
