from pathlib import Path


def render_iot_schedule(results) -> None:
    print("IoT offloading schedule (local device or edge server per task)")
    for row in results:
        location = (
            f"DEV={row.device_id}" if not row.was_offloaded else f"S={row.server_id}"
        )
        overhead = "-" if not row.was_offloaded else f"{row.transfer_overhead:.2f}"
        print(
            f"[{row.task_id}] {row.task_name} | {location}, "
            f"r={row.arrival_time:.2f}, C={row.execution_time:.2f}, "
            f"d={row.assigned_deadline:.2f}, "
            f"t={overhead}, "
            f"svc=[{row.service_start_time:.2f}, {row.service_finish_time:.2f}]"
        )


def save_iot_gantt_plot(
    results,
    output_path: str,
) -> Path:
    import matplotlib.pyplot as plt

    fig_height = max(4, len(results) * 0.55)
    fig, ax = plt.subplots(figsize=(12, fig_height))

    y_ticks = []
    y_labels = []

    for i, row in enumerate(results):
        y = i * 10
        duration = row.service_finish_time - row.service_start_time
        if row.was_offloaded:
            label = f"S{row.server_id} [{row.task_id}] {row.task_name}"
            face = "#457B9D"
            edge = "#1D3557"
        else:
            label = f"DEV{row.device_id} [{row.task_id}] {row.task_name}"
            face = "#2A9D8F"
            edge = "#264653"

        ax.broken_barh(
            [(row.service_start_time, duration)],
            (y, 7),
            facecolors=face,
            edgecolors=edge,
            linewidth=1.0,
        )
        ax.scatter(row.arrival_time, y + 3.5, color="#E76F51", s=18, zorder=3)
        ax.scatter(row.assigned_deadline, y + 3.5, color="#1D3557", s=18, zorder=3)

        y_ticks.append(y + 3.5)
        y_labels.append(label)

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_xlabel("Time")
    ax.set_ylabel("IoT Tasks")
    ax.set_title("IoT Offloading Schedule Gantt")
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.margins(x=0.02)

    plt.tight_layout()
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output
