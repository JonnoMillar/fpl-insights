"""Cheap Windows availability check; queue this chat only when a review is due."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
THREAD = "01a184da-650d-7622-980e-08411e45e49a"


def timestamp(value):
    if not value:
        return None
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp needs a timezone")
    return result


def due(now, review, account, dispatch):
    if review.get("disabled"):
        return False, "Account management disabled"
    last = timestamp(review.get("last_completed_utc"))
    if last and last > now:
        return False, "Review clock is ahead; investigate clock"
    attempted = timestamp(dispatch.get("last_attempt_utc"))
    pending = timestamp(dispatch.get("queued_utc"))
    if pending and (not last or last < pending) and now - pending < timedelta(hours=6):
        return False, "Review already queued"
    if attempted and now - attempted < timedelta(hours=1):
        return False, "Dispatch retry cooldown"
    blocked = timestamp(review.get("last_blocked_utc"))
    if blocked and (not last or blocked > last) and now - blocked < timedelta(hours=6):
        return False, "Blocked review cooldown"
    if not last:
        return True, "No completed review recorded"
    deadline = timestamp(account.get("next_deadline_utc"))
    age = now - last
    if deadline:
        remaining = deadline - now
        if deadline <= now and last < deadline:
            return True, "Catch up after gameweek deadline"
        if timedelta(0) < remaining <= timedelta(hours=2) and age >= timedelta(minutes=45):
            return True, "Final deadline review"
        if timedelta(0) < remaining <= timedelta(hours=24) and age >= timedelta(hours=6):
            return True, "Pre-deadline review"
    return age >= timedelta(hours=56), "Routine review interval"


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def codex_command():
    # Desktop updates can replace the versioned binary directory.
    found = shutil.which("codex")
    if found:
        return found
    candidates = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI/Codex/bin").glob("*/codex.exe"))
    if not candidates:
        raise RuntimeError("Codex CLI not found")
    return str(max(candidates, key=lambda item: item.stat().st_mtime))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    account = read(ROOT / "state.json")
    review = read(ROOT / "review-status.json")
    dispatch_path = ROOT / "private/startup-dispatch.json"
    dispatch = read(dispatch_path)
    required, reason = due(now, review, account, dispatch)
    print(json.dumps({"due": required, "reason": reason, "dry_run": args.dry_run}))
    if not args.dry_run:
        dispatch.update(last_checked_utc=now.isoformat(), due=required, reason=reason)
        save(dispatch_path, dispatch)
    if not required or args.dry_run:
        return
    # Task Scheduler IgnoreNew serialises launcher calls; persist before dispatch
    # so a timeout does not immediately enqueue the same request again.
    dispatch["last_attempt_utc"] = now.isoformat()
    save(dispatch_path, dispatch)
    prompt = (
        "Availability-triggered FPL catch-up for entry 11195024. "
        "Read account-management/HANDOFF.md, startup-operation.md, review-status.json "
        "and state.json first. Recheck whether a review is due before doing any work; "
        "a duplicate queued prompt must not repeat a recent completed review. "
        "Apply the existing strategy and authority, check current public deadline and "
        "news and the real signed-in team, then save/reload/verify any justified changes. "
        "Record completion in review-status.json only after the review really completes, "
        "including a valid no-change decision. If blocked, record last_blocked_utc and "
        "the blocker instead; do not advance last_completed_utc. "
        "Never change the dashboard or other account. No hits/chips. "
        "Quiet unless meaningful changes, failure or user action are needed. "
        "This trigger proves the launcher ran, not that the browser is available."
    )
    try:
        result = subprocess.run(
            [codex_command(), "queue", "--thread", THREAD, "--message", prompt],
            capture_output=True, text=True, timeout=45, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        dispatch["error"] = str(exc)
        save(dispatch_path, dispatch)
        raise
    dispatch.update(queued_utc=now.isoformat(), result=result.stdout.strip(), error=None)
    save(dispatch_path, dispatch)


if __name__ == "__main__":
    main()
