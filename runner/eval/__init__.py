"""runner.eval — Tony's walk-forward evaluation harness (Project Lighthouse, T1.1).

The keystone safety gate: replays RECORDED verdicts/outcomes/realized history, graded
walk-forward (train past / test held-out future) to answer "does a candidate change improve
out-of-sample outcomes WITHOUT regressing a guardrail?" — before it can touch real money.
Learns from the REAL realized track, never the rosy verdict track (the audit invariant).
"""
