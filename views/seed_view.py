def render_seed_skipped() -> None:
    print("Seed skipped: tasks already exist. Use --force to replace with seed tasks.")


def render_seed_reset(removed: int) -> None:
    print(f"Seed reset: removed {removed} existing task(s).")


def render_seed_complete(created: int) -> None:
    print(f"Seed complete: created {created} task(s).")
