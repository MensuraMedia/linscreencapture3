# Pending

- 2026-10-18: PRs into `feat/phase5`, in this order: `fix/tray-alttab-icons` (must land first: without it `make test`
  deletes the real autostart entry), `feat/editor-shadows-canvas` (preview fix, shadow switches, pasted-image shadow,
  page growth; contains the docs branch), `feat/clip-tray-4up` (4-up clipboard tray, reviewed; stacked on `feat/editor-shadows-canvas`).
  Session record and open questions: `docs/CHANGES-2026-10-18.md` (§6 questions, §7 what remains). HANDOFF §0a.
- Phases 1–5: done; awaiting the operator's on-screen sign-off and the PR into `main`.
- Phase 6 (HANDOFF §8): done — background agent, tray, hotkey capture (any recorded key), Run at startup, System page
  (partly), Cinnamon registrar, Region Plus, clipboard-first capture, install.sh + .deb, app icon. To do — registrar for
  GNOME / Xfce / MATE, countdown chip, pin to screen, scrolling capture, include pointer, rest of the System page and the
  Shortcuts page, their tests; then the operator's sign-off.
- Page growth follow-up: the dashed future-page outline while dragging (`docs/EDITOR-CANVAS-EXPANSION.md` §4.3).
- s049 i18n strategy (`docs/s049_i18n_strategy.md`) on branch `docs/i18n-strategy` — local only on the second machine,
  not pushed; awaiting operator review before any string-wrapping pass.
- Snapshot tool caveat: on a fresh clone, `make snapshot` falls back to the real Pictures folder for the Library render
  until the tool defaults the folder to `screenshots/fixtures/`.
- `AGENTS.md` / `KNOWN_ISSUES.md` say xvfb is installed on the dev machine: true for one machine only.
- `feat/background-agent` on origin is stale (`47fe0a0`); delete once nothing refers to it.
