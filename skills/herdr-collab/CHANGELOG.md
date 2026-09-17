# Changelog

All notable changes to the `herdr-collab` skill.
Format: Keep a Changelog; versioning: SemVer. Versions are tagged `herdr-collab/vX.Y.Z`.

## 0.1.1 - 2026-09-17

- Extend the standalone skill to inspect layout, create a sibling pane, run ordinary
  pane commands, start agents, and support explicit saved-machine selectors.
- Adopt CLI status/compatibility checks, authoritative JSON IDs, `--no-focus`, output
  source guidance, repository trust boundaries, and server-stop safeguards.
- Keep peer collaboration hardening: self-target rejection, strict idle/done
  verification, blocked-dialog escalation, and inspect-before-resubmit after stalls.

## 0.1.0 - 2026-09-17

Initial release.

- Peer discovery via `herdr agent list` with resolution rules: explicit name/pane ID
  first, same-workspace preference, eligibility = `idle`/`done` only.
- Verification step (`agent get` + short `agent read`) required before prompting.
- Work handoff via `agent prompt --wait` with self-contained prompts; timeout/stall
  handling that inspects before re-submitting.
- `agent wait --until idle --until done --until blocked --until unknown` for busy peers;
  `blocked` handling surfaces approval dialogs to the human, never auto-answers.
- Result collection via `agent read --source recent-unwrapped`; file-handoff fallback
  for oversized responses.
- Hard rules: gate on `HERDR_ENV=1`, no targeting by kind/title/order, never
  auto-prompt a `working`/`blocked`/`unknown` peer, attribute peer output.
