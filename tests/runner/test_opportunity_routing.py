import pytest
import runner.tasks.router as r


@pytest.fixture(autouse=True)
def _reset_routing():
    r._routing_table = None
    yield
    r._routing_table = None


def test_scout_routes_to_opportunity_worker():
    assert r.route_task({"task_type": "opportunity_scout"}) == "opportunity_worker"


def test_spec_routes_to_opportunity_worker():
    assert r.route_task({"task_type": "opportunity_spec"}) == "opportunity_worker"


def test_poc_build_routes_to_forge():
    assert r.route_task({"task_type": "poc_build"}) == "heavy_worker"


def test_poc_grade_routes_to_opportunity_worker():
    # C-seam: grading currently routes back to Prospector
    assert r.route_task({"task_type": "poc_grade"}) == "opportunity_worker"
