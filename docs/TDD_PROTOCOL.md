# TDD Protocol (Adopted)

Effective immediately, all development follows Test-Driven Development (TDD).

## Core Rules
- Write tests first (unit/integration) that describe desired behavior.
- Implement the minimal code to make tests compile and run.
- Run tests frequently; iterate until tests pass.
- Refactor with tests green; repeat.
- Only then update documentation, commit, and push.
- Proceed to the next task only after all tests for the current task are passing.

## Workflow Steps
1. Create/Update tests for the task.
2. Run tests; confirm they fail (red).
3. Implement code to satisfy tests.
4. Run tests until green (unit + integration when applicable).
5. Update docs (README/PRD/API docs) as necessary.
6. Commit with clear message referencing Task Master task ID.
7. Push to remote.
8. Move to next Task Master task.

## Tooling
- Python: pytest (see tests/)
- TypeScript/Functions: jest (npm test)
- UI: React testing library / jest
- CI (future): GitHub Actions to enforce test runs on PRs

## Task Master Integration
- Every task/subtask includes an explicit "Write tests first" item.
- Use `task-master update-subtask --id=<id> --prompt="TDD: tests first, then impl"` when starting.
- Mark as done only when tests pass locally.

