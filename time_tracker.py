from database import get_time_summary, get_token_total


def format_report(session_id: int, conn) -> str:
    summary = get_time_summary(conn, session_id)
    tokens = get_token_total(conn, session_id)
    # Estimate cost: ~$3/M input + $15/M output tokens; use blended ~$4/M
    cost = tokens * 4 / 1_000_000

    lines = ["  Today's Time Summary", "  " + "─" * 28]
    total = 0
    for task, secs in sorted(summary.items(), key=lambda x: -x[1]):
        lines.append(f"  {task:<22} {_fmt(secs):>6}")
        total += secs
    lines.append("  " + "─" * 28)
    lines.append(f"  {'Total focused time':<22} {_fmt(total):>6}")
    lines.append(f"\n  API calls: {tokens:,} tokens  (~${cost:.3f})")
    return "\n".join(lines)


def _fmt(secs: int) -> str:
    h, m = divmod(secs // 60, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"
