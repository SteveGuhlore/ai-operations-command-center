# File Ownership Rules

Every task must list:

- files to inspect
- files allowed to change
- files forbidden to change

No worker can edit outside allowed files.

If a task requires another file, the worker must stop and request task expansion.

Parallel-safe tasks must not overlap allowed files unless they are docs-only and Codex approves.
