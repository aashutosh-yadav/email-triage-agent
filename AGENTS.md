# Agent Skills

This project uses the `addyosmani/agent-skills` pack, loaded from
`~/agent-skills/skills` via the `skills` config in `opencode.jsonc`.

## Core rules

- If a task matches a skill, load it with the `skill` tool before acting.
  Pass the skill ID (not a display name), e.g. `skill({ id: "code-review-and-quality" })`.
- Follow the skill workflow fully. Do not partially apply it.
- Never skip required steps such as spec, plan, or test when a skill demands them.

## Intent to skill mapping

- Feature / new functionality -> `spec-driven-development`, then
  `incremental-implementation` and `test-driven-development`
- Planning / breakdown -> `planning-and-task-breakdown`
- Bug / failure / unexpected behavior -> `debugging-and-error-recovery`
- Code review -> `code-review-and-quality`
- Refactoring / simplification -> `code-simplification`
- API or interface design -> `api-and-interface-design`
- UI work -> `frontend-ui-engineering`
- Email triage decisions (category, priority, action, reply) -> `email-triage-policy`
- Building the email triage agent -> `terminal-triage-agent`

## Project-local skills

Challenge-specific skills live in `.opencode/skills/`:

- `email-triage-policy` — the taxonomy, priority/action rule tables, and reply
  policy under `references/`. This is the source of truth for triage decisions;
  reuse its `references/*.md` in the built agent's prompt rather than copying.
- `terminal-triage-agent` — the build workflow (I/O contract, model/code split,
  validation, eval, README).

## Execution model

For every request:

1. Decide whether any skill applies (even a small chance).
2. Load it with the `skill` tool using its exact ID.
3. Follow the skill workflow.
4. Only start implementation once the skill's required steps are done.
