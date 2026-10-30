# Login recovery

Jonno confirmed **Google sign-in**, and explicitly authorised automatic FPL
login recovery for this managed account on 29 October 2026.

## Verified recovery test

On 29 October, the agent signed out of FPL, clicked **Log in**, then **Sign in
with Google**. Google's account chooser offered Jonno Millar's existing signed-in
identity. Selecting it led to an additional-access screen. The optional date of
birth and personal-phone-number permissions were left unchecked; **Continue**
completed ordinary sign-in using existing permissions. No password, code,
device approval, new permissions or account changes were needed.

FPL returned to Pick Team. The saved squad, Haaland captain, Van Hecke vice,
bench order and £0.4m bank were unchanged. Clicking the account's Gameweek History
link verified **/en/entry/11195024/history**. Screenshot evidence is in ignored
`.cache/google-relogin.png`. The account was left signed in on Pick Team.

The same recovery succeeded during the unattended 30 October pre-deadline review:
FPL was signed out and Google remained available; no user input was needed.
This proves FPL recovery while the existing Google session works. It does not
prove recovery after Google logs out or establish a guaranteed session lifetime.

Jonno later reported completing the FPL password-reset form. A local DPAPI
credential helper was prepared, but its Save prompt failed to load the Windows
PowerShell security module and no credential was saved. Password login remains
unverified and must not replace the tested Google path until setup is completed.

## Procedure on future reviews

1. Open the existing FPL browser session and check whether the real managed
   account is already accessible. Do not sign out just to test on each review.
2. If FPL is signed out, use its normal **Log in → Sign in with Google** flow.
   Use Jonno's previously verified Google identity. If multiple identities make
   the intended account unclear, ask rather than guessing or creating a team.
3. Leave optional additional Google permissions unchecked. Continue using
   existing access only. Stop for any materially expanded permission request,
   changed terms requiring acceptance, unexpected destination or security warning.
4. After redirect, verify the account's own history link identifies entry
   **11195024** before any team write. Reconcile actual saved team and budget.
5. If Google asks for a password, passkey, device approval, code or other
   challenge, record the concrete blocker and ask Jonno to complete normal login
   in that browser. Do not extract cookies/tokens, copy another profile, disable
   security features or promise uninterrupted access. Avoid repeated attempts.

No Google password or authentication token is stored by this project. Existing
browser sessions are the mechanism. Recovery is a normal authorised sign-in,
not a permanent replacement for Google verification.
