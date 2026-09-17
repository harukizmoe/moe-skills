# Changelog

All notable changes to the `herdr-collab` skill.
Format: Keep a Changelog; versioning: SemVer. Versions are tagged `herdr-collab/vX.Y.Z`.

## 0.1.0 - 2026-09-17

Initial release.

- Peer discovery via `herdr agent list` with resolution rules: explicit name/pane ID
  first, same-workspace preference, eligibility = `idle`/`done` only.
- Verification step (`agent get` + short `agent read`) required before prompting.
- Work handoff via `agent prompt --wait` with self-contained prompts; timeout/stall
  handling that inspects before re-submitting.
- `agent wait --until idle` for busy peers; `blocked` handling surfaces approval
  dialogs to the human, never auto-answers.
- Result collection via `agent read --source recent-unwrapped`; file-handoff fallback
  for oversized responses.
- Hard rules: gate on `HERDR_ENV=1`, no targeting by kind/title/order, never
  auto-prompt a `working`/`blocked`/`unknown` peer, attribute peer output.
