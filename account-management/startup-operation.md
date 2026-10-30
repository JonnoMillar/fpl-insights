# Availability-triggered operation

Jonno requested catch-up reviews when the laptop is available, roughly three
times per week, instead of depending on being online at fixed review times.

The Windows task **FPL account catch-up** runs as the current interactive user,
90 seconds after sign-in and every 30 minutes while available. It does not wake
the computer, request elevation, store a password, or run an AI review on each
tick. `pythonw.exe startup_check.py` checks local timestamps first. If due, the
installed `codex queue` command requests work in the existing managed-account
chat. Queue acceptance is not evidence that a review ran or browser access worked.
The installer also adds a per-user `FPL Codex.lnk` Windows Startup shortcut to
open the installed desktop app at sign-in, ahead of the 90-second check. It does
not sign into FPL or guarantee that the browser session survives restarting.

Routine reviews are due after **56 hours** since a completed review (roughly
three per week if the laptop is available). Additional reviews are due after
six hours when within 24 hours of the recorded deadline, and after 45 minutes
when within two hours. If the last review predates a deadline that has passed,
catch up immediately. The agent must refresh the actual next deadline each
review; the launcher's recorded deadline is only a trigger hint.

An accepted queue request has a six-hour duplicate suppression window; dispatch
failures have a one-hour retry delay. A blocked review has a six-hour delay.
Unchanged login failures should not generate repeated notifications. These are
best-effort guards, not an exactly-once queue. On receipt of a queued request,
recheck `review-status.json` and call the launcher's `due` function with an empty
dispatch dictionary: the queue itself must not suppress its own processing.
If a newer review already completed and no review is due, stop without changes.
Never run concurrent account writes. If an earlier run might have written,
inspect the actual team before retrying.

## Review completion contract

- Start by reading account HANDOFF, state, strategy and rules. Operate entry
  11195024 only, under existing authority. No points hits or chips.
- A completed review includes fresh deadline/data/news checks, authenticated
  account reconciliation, and a justified change or explicit no-change decision.
  Reload and verify every account write. Update `state.json` and dated decision
  evidence as needed. Then update `review-status.json`: `last_completed_utc`,
  `last_result`; clear `last_blocked_utc` and `blocker`.
- An unavailable browser, expired login or material missing data is a blocked
  review: set `last_blocked_utc` and `blocker`, preserve the previous successful
  completion timestamp and legal saved team. Never count an attempted or merely
  queued run as completion. Notify once per distinct actionable blocker.
- Use the existing browser session. If FPL is signed out, first follow
  `authentication.md`: ordinary Google sign-in through Jonno's existing Google
  session was tested successfully. Ask for help only if recovery is blocked.
  No measured session lifetime is known. Do
  not promise persistent login, use keep-alive tricks, copy cookies/passwords,
  bypass verification, or reuse the other account's credentials. Ask Jonno to
  log in normally when Google itself needs authentication; after confirmation,
  retry the blocked review.
- At season end, set `disabled: true` in review-status and disable the Windows
  task and heartbeat.

The old heartbeat remains only as a daily fallback, subject to the same due
check. It must use this contract rather than changing its own frequency. This
avoids two separate policies and fixed-time full reviews.

## Maintenance and verification

`private/startup-dispatch.json` (ignored, no credentials) records local checks,
queue acceptance and errors. Review success is recorded separately in tracked
`review-status.json`. To inspect or test:

```powershell
python account-management/startup_check.py --dry-run
python -m unittest discover -s account-management -p test_startup.py -v
Get-ScheduledTask -TaskName 'FPL account catch-up'
Get-ScheduledTaskInfo -TaskName 'FPL account catch-up'
```

Reinstall idempotently with `account-management/install-startup.ps1`. Disable
with `Disable-ScheduledTask -TaskName 'FPL account catch-up'`; remove with
`Unregister-ScheduledTask -TaskName 'FPL account catch-up' -Confirm:$false`.
Remove the optional app auto-start shortcut from the Windows Startup folder
(`shell:startup`) by deleting `FPL Codex.lnk`. Implementation and runtime files
stay within this account directory; only the task registration and this shortcut
are installed in Windows.

Verified: CLI transport probe executed in this chat; due-check boundary tests
pass. The first unattended no-change review and Google recovery completed on
30 October. Windows reboot/sign-in delivery and unattended account writes still
need separate verification; this is not proof of every execution path.
