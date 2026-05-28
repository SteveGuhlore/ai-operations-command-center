# Next Steps

## Immediate safe actions

1. Reopen the command center folder on the home machine.
2. Run the full validation set.
3. Install Node.js and npm if needed.
4. Install Star Office UI separately.
5. Test the local dashboard launch helpers and exported dashboard state.
6. Reset sample tasks if you want to repeat dry-run behavior.
7. Run dry-run only and confirm task movement, logs, and reports still look correct.
8. Connect the first real project profile only after validations still pass.

## Recommended next build phase

### 1. Project profile connection

Add a real project profile only after choosing a target workspace and keeping placeholder-safe validation rules.

### 2. Real model provider adapter

Add a provider adapter layer that maps generic role IDs to configurable providers and model labels without breaking the current role abstractions.

### 3. Dashboard bridge

Turn `dashboard-push.ps1` into a safe read-only summary exporter for the visual UI layer.

### 4. Scheduler/daemon

Add a safe recurring runtime for health checks, queue scans, and reporting without enabling autonomous risky actions.

### 5. Revenue pod activation

Choose one pod, keep it approval-gated, and start with first safe tasks only.

## Keep these stop conditions

- No API connections without explicit approval.
- No real worker launch without explicit approval.
- No spending, purchasing, or publishing without explicit approval.
- No credentials in files.
- No external account actions without explicit approval.
- No autonomous trading.
