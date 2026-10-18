# LinScreenCapture 3 (linscreencapture3) — project instructions

Workspace scope. Global standards load first from ~/.zcode/AGENTS.md; this file
only adds what is specific to this project. Additive changes only — never modify
universal standards here.

- Description: Python 3 + GTK4/libadwaita rebuild of the 1.4 C/GTK3 screenshot tool; Studio Editor shell, phases 1-5 done, phase 6 in progress (branch feat/phase5)
- Bootstrapped: 2026-10-12 by s003_workspace_bootstrap_a.sh
- Ledger: ~/projects/Zai-ZCode/s-register.md

## Stack

- Python 3.12, GTK 4.14.5, libadwaita 1.5, PyGObject 3.48, pycairo, Pillow 10.2, numpy, python-xlib (system packages; no pip manifest)
- Run: `make resources && python3 -m linscreencapture` (`--debug` or `LSC_DEBUG=1` for verbose logging)
- Test: `make test` → pytest (131 tests; runs under `xvfb-run` when installed, which it is on the dev machine since 2026-10; otherwise the live display. Under Xvfb `test_window_geometry` and `test_close_saves_settings` fail by 10 px — no window manager)
- Renders: `make snapshot` → `screenshots/dev/shell_*.png`; icons: `make icons`, `make launcher`
- Dev machine: Linux Mint Cinnamon on X11

## Project rules

- Capture behaviour: `docs/CAPTURE.md` is authoritative (hotkey, agent, modes, overlay, clipboard, save path); fix it or the code in the same change when they disagree.
- Authoritative docs: `docs/GUI_SPEC.md` for the GUI, `HANDOFF.md` for process and state. Keep `docs/FEATURES.md`, `HANDOFF.md` and `changelog.md` current with every change.
- `changelog.md` is git-ignored by family convention — local-only, still append-only.
- Privacy (public repo): never commit real desktop/overlay captures. Overlay renders go to git-ignored `screenshots/dev/overlay.png`; README/Library renders use the tracked synthetic fixtures in `screenshots/fixtures/`.
- Phase gating: each phase waits for the operator's on-screen sign-off of the previous one. Phase 6 scope and checklist: HANDOFF.md §8. The legacy C sources were deleted in Phase 5; the 1.4 behaviour reference is the original repository.
- Feature/doc work happens on dedicated branches (`feat/…`, `docs/…`); `main` stays release-facing.
- Never `pkill -f "python3 -m linscreencapture"` from an agent shell — the pattern matches the agent's own shell (HANDOFF §6).

## Change tracking

- changelog.md at repo root — append-only; every completed change gets an entry

## Memory

- .zcode/memory/decisions.md — architectural decisions with rationale
- .zcode/memory/pending.md — unfinished work carried between sessions
