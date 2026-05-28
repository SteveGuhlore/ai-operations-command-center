# Codex Home Handoff Prompt

```text
You are the command center manager.

We are preparing to review the reusable AI Agent Command Center foundation locally.

Important:
- The Reddit-style framework is the blueprint:
  manager -> task pool -> locks -> worker loops -> logs -> review -> repeat.
- Role strategy:
  manager = reviewer/coordinator
  heavy_worker = heavy implementation
  debug_worker = debugger/test fixer/docs
- Safety:
  no real worker launch without explicit approval, no external project edits, no .env edits, no secrets, no live APIs.

Do not edit yet.

Audit:
1. Command center folder structure.
2. Sample project profile.
3. Task pool files.
4. Lock/log/report scripts.
5. Home setup checklist.
6. Dry-run first run plan.

Then produce:
- readiness score from 0 to 100
- missing pieces
- exact safe next command
- exact stop conditions
- whether we are ready for dry-run only or real worker run
```
