import os
from dataclasses import dataclass, field
import anthropic
from config import CLAUDE_MODEL, ACTIVITY_LOG_CONTEXT

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


@dataclass
class AnalysisResult:
    doing: str = ""
    category: str = "unknown"      # productive | drift | break | unknown
    confidence: float = 0.0
    inferred_task: str = "none"
    nudge_text: str = ""
    focus: str = ""
    tokens_used: int = 0
    error: str = ""


_FALLBACK = AnalysisResult(
    nudge_text="Claude is unavailable — stay on task!",
    category="unknown",
)


def _build_prompt(
    app_name: str,
    window_title: str,
    tasks: list[str],
    recent_log: list[dict],
    next_commitment: str,
) -> str:
    task_list = "\n".join(f"- {t}" for t in tasks) if tasks else "(none entered)"

    log_lines = []
    for entry in recent_log[-ACTIVITY_LOG_CONTEXT:]:
        if entry.get("skip_reason"):
            log_lines.append(f"  [{entry['timestamp']}] skipped ({entry['skip_reason']})")
        else:
            log_lines.append(
                f"  [{entry['timestamp']}] {entry.get('inferred_task','?')} — {entry.get('category','?')}: {entry.get('claude_summary','')}"
            )
    log_text = "\n".join(log_lines) if log_lines else "  (no prior activity this session)"

    commitment_line = f"My next hard commitment is at: {next_commitment}" if next_commitment else "No scheduled commitment right now."

    return (
        f"Active app: {app_name} — \"{window_title}\"\n\n"
        f"My task list for today:\n{task_list}\n\n"
        f"Recent activity (last {ACTIVITY_LOG_CONTEXT} cycles):\n{log_text}\n\n"
        f"{commitment_line}\n\n"
        "You are a warm, supportive productivity companion — never judgmental or harsh. "
        "The user is doing their best. If what you see doesn't obviously match their task list, "
        "assume there's a good reason (research, a related subtask, a quick break). "
        "Only flag drift if you're genuinely confident (confidence > 0.7). "
        "Keep nudges short, kind, and encouraging — like a friend checking in, not a boss auditing.\n\n"
        "Based on the screenshot and context above, respond ONLY in this exact format "
        "(no extra text before or after):\n"
        "DOING: <one sentence describing what the user appears to be doing>\n"
        "CATEGORY: <productive|drift|break|unknown>\n"
        "CONFIDENCE: <0.0 to 1.0 — how sure you are about the category>\n"
        "TASK: <exact task name from list that best matches, or 'none'>\n"
        "NUDGE: <1-2 sentences — warm and encouraging, never scolding>\n"
        "FOCUS: <a gentle, specific suggestion for what to tackle next>"
    )


def _parse_response(text: str) -> dict:
    result = {
        "doing": "", "category": "unknown", "confidence": 0.0,
        "inferred_task": "none", "nudge_text": "", "focus": "",
    }
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        k = key.strip().upper()
        if k == "DOING":
            result["doing"] = val
        elif k == "CATEGORY":
            result["category"] = val.lower() if val.lower() in ("productive", "drift", "break", "unknown") else "unknown"
        elif k == "CONFIDENCE":
            try:
                result["confidence"] = min(1.0, max(0.0, float(val)))
            except ValueError:
                pass
        elif k == "TASK":
            result["inferred_task"] = val
        elif k == "NUDGE":
            result["nudge_text"] = val
        elif k == "FOCUS":
            result["focus"] = val
    return result


def analyze_screen(
    b64_jpeg: str,
    app_name: str,
    window_title: str,
    tasks: list[str],
    recent_log: list[dict],
    next_commitment: str,
) -> AnalysisResult:
    prompt = _build_prompt(app_name, window_title, tasks, recent_log, next_commitment)
    try:
        response = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            timeout=30,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64_jpeg,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = response.content[0].text
        parsed = _parse_response(raw)
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return AnalysisResult(**parsed, tokens_used=tokens)

    except anthropic.AuthenticationError as e:
        return AnalysisResult(error=f"auth_error:{e}", nudge_text="API key invalid — check your .env file.")
    except anthropic.RateLimitError:
        return AnalysisResult(error="rate_limit", nudge_text="Rate limited — will retry soon.")
    except anthropic.APIConnectionError:
        return AnalysisResult(error="connection", **{k: v for k, v in vars(_FALLBACK).items() if k != "error"})
    except Exception as e:
        return AnalysisResult(error=str(e), nudge_text="Claude unavailable — stay on task!")


def chat_with_claude(
    message: str,
    tasks: list[str],
    current_task: str,
    next_commitment: str,
) -> str:
    """Send a freeform chat message and return Claude's plain-text reply."""
    task_list = "\n".join(f"- {t}" for t in tasks) if tasks else "(none)"
    system = (
        "You are a warm, supportive productivity companion embedded in a desktop widget. "
        "Be concise (2-4 sentences max), kind, and practical — like a smart friend helping out. "
        "Never judge or scold. Assume the user is doing their best. "
        f"Their task list today: {task_list}. "
        f"Current task: {current_task}. "
        f"Next commitment: {next_commitment or 'none'}."
    )
    try:
        response = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            timeout=30,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Couldn't reach Claude: {e}"
