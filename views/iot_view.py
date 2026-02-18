from pathlib import Path


def render_iot_schedule(results) -> None:
    print("IoT offloading schedule (local device or edge server per task)")
    for row in results:
        location = (
            f"DEV={row.device_id}" if not row.was_offloaded else f"S={row.server_id}"
        )
        overhead = "-" if not row.was_offloaded else f"{row.transfer_overhead:.2f}"
        decision = f"{row.decision_time:.2f}" if row.decision_time else "-"
        print(
            f"[{row.task_id}] {row.task_name} | {location}, "
            f"r={row.arrival_time:.2f}, C={row.execution_time:.2f}, "
            f"d={row.assigned_deadline:.2f}, "
            f"t={overhead}, "
            f"decision={decision}, "
            f"svc=[{row.service_start_time:.2f}, {row.service_finish_time:.2f}]"
        )


def save_iot_gantt_plot(
    results,
    output_path: str,
) -> Path:
    import matplotlib.pyplot as plt

    lane_labels = []
    lane_index: dict[str, int] = {}
    for row in results:
        label = f"S{row.server_id}" if row.was_offloaded else f"DEV{row.device_id}"
        if label not in lane_index:
            lane_index[label] = len(lane_labels)
            lane_labels.append(label)

    fig_height = max(4, len(lane_labels) * 1.1)
    fig, ax = plt.subplots(figsize=(12, fig_height))

    y_ticks = [idx * 10 + 3.5 for idx in range(len(lane_labels))]

    for row in sorted(results, key=lambda item: (item.service_start_time, item.task_id)):
        lane = f"S{row.server_id}" if row.was_offloaded else f"DEV{row.device_id}"
        y = lane_index[lane] * 10
        duration = row.service_finish_time - row.service_start_time
        if row.was_offloaded:
            face = "#457B9D"
            edge = "#1D3557"
        else:
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
        ax.text(
            row.service_start_time + (duration * 0.02),
            y + 3.5,
            row.task_id,
            fontsize=7,
            va="center",
            ha="left",
            color="#111111",
        )

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(lane_labels)
    ax.set_xlabel("Time")
    ax.set_ylabel("Execution Resource")
    ax.set_title("IoT Offloading Schedule Gantt")
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.margins(x=0.02)

    plt.tight_layout()
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output
