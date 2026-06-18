# Test baseline (review/autofix-2026-06-17)
Tony-Stocks: 1257 passed, 0 failed (PYTHONPATH=src python -m pytest)
AI Ops: 947 passed, 4 FAILED (pre-existing, quarantined):
  - tests/runner/test_eval_harness.py::test_harness_reproduces_live_scorecard_baseline
  - tests/runner/test_research_wave.py::test_wave_enqueues_once_and_dedups
  - tests/runner/test_stress_round2.py::test_reaper_reaps_task_with_dead_owner
  - tests/runner/test_tony_enrichment_blocks.py::test_lessons_block_empty_without_data
Gate: no NEW failures beyond these.
