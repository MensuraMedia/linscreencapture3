# Pending

No pending items.

- Phase 5 (image operations and files) is next; gated on the operator's on-screen sign-off of Phase 4. Checklist: HANDOFF.md §8. Ends with deleting the legacy C sources and updating README/INSTALL/KNOWN_ISSUES/FEATURES.
- s049 i18n strategy (docs/s049_i18n_strategy.md) on branch docs/i18n-strategy — awaiting operator review before any string-wrapping pass (wrap before Phase 5 per plan).
- Branch docs/app-screenshots: 3 commits unpushed (cbaed3b, eba9388, e9d017c) — awaiting operator review.
- Snapshot tool caveat: on a fresh clone, `make snapshot` falls back to the real Pictures folder for the Library render until the tool defaults the folder to screenshots/fixtures/.
