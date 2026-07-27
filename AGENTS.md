# Project Agent Instructions

## Current work

- Continue the Muse trial-runner Task 8 work from `.superpowers/sdd/progress.md`.
- Preserve all existing user and uncommitted changes. Do not reset, discard, or overwrite the dirty working tree.
- Follow the approved Subagent-Driven workflow: one implementer at a time, then an independent spec and code-quality review for that task.
- Use test-driven development for behavior changes and bug fixes.

## Verification constraints

- Do not run application build commands unless the user explicitly changes this instruction.
- Focused Backend and Angular tests are allowed.
- Do not open a browser. Headless test runners are allowed.
- Do not claim completion without fresh test and review evidence.

## Product constraints

- This is an entertainment/prototype project, not a medical product.
- Keep the approved “Creative Headset Setup” product direction.
- Keep component styles in separate stylesheet files; do not add inline CSS or `style` attributes.
- Login remains a single entry point and routes users by their stored role.

## Task 8 safety

- Live database migration `20260719_03` must not be applied until a fresh, nonempty schema-only backup has been created and verified.
- Do not commit `backend/.env`, database dumps, or unrelated `.superpowers/sdd` scratch artifacts.
- Keep device/deployment hardening and signal/media integrity fixes in separate commits and review each independently.
