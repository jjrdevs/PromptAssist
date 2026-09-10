# Project AI Development Instructions

This file is the single source of truth for the AI's behavior in this repository.
It is rendered by `passist sync-agent` into the per-tool agent files
(`CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `GEMINI.md`) with a
tool-specific one-line header.

## General Development Rules

Before making changes:

- Understand the existing architecture.
- Review relevant documentation in `docs/`.
- Identify existing systems before creating new ones.
- Do not assume missing information.

If information is missing:

1. State what information is missing.
2. Explain why it affects the implementation.
3. Ask for clarification before proceeding.

## Documentation Rules

Documentation represents the intended architecture.

When code and documentation conflict:

1. Identify the conflict.
2. Determine whether the implementation is incorrect or the documentation needs updating.
3. Update the appropriate source.

Do not silently change architecture.

## Planning Rules

Before implementing major features, create a development plan at
`docs/development/{feature_name}_plan.md` containing:

- Feature purpose
- Architecture changes
- Files affected
- Dependencies
- Implementation phases
- Testing requirements
- Risks and failure points

Do not begin implementation until the plan has been reviewed.

## Implementation Rules

When developing:

- Follow existing architecture patterns.
- Prefer modifying existing systems over creating duplicates.
- Keep responsibilities separated.
- Avoid unnecessary refactoring.
- Do not introduce systems that are not required.

Before large changes, explain:

- What files will change.
- Why they need changing.
- How the changes satisfy the plan.

## Progress Tracking

For multi-step features maintain `docs/development/{feature_name}_progress.md`.
Update it with:

- Completed tasks
- Files modified
- Remaining work
- Known issues
- Decisions made

## Architecture Decisions

For significant design decisions, create an ADR at `docs/adr/{decision_name}.md`.
Include:

- Context
- Problem
- Considered solutions
- Chosen solution
- Consequences

## Completion Verification

Before declaring a feature complete, audit against:

- Development plan
- Documentation
- Existing architecture

Check:

- All requirements implemented
- No missing dependencies
- No unfinished tasks
- No documentation gaps
- No obvious edge cases
