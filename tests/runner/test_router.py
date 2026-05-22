from runner.tasks.router import route_task


def test_routes_validation_to_debug_worker():
    task = {"task_type": "validation", "assigned_agent": "debug_worker"}
    assert route_task(task) == "debug_worker"


def test_routes_implementation_to_heavy_worker():
    task = {"task_type": "implementation"}
    assert route_task(task) == "heavy_worker"


def test_routes_content_drafting_to_content_worker():
    task = {"task_type": "content_drafting"}
    assert route_task(task) == "content_worker"


def test_falls_back_to_assigned_agent_when_type_unknown():
    task = {"task_type": "unknown_type_xyz", "assigned_agent": "heavy_worker"}
    assert route_task(task) == "heavy_worker"


def test_falls_back_to_debug_worker_when_nothing_matches():
    task = {"task_type": "unknown_type_xyz"}
    assert route_task(task) == "debug_worker"


def test_uses_assigned_agent_when_no_task_type():
    task = {"assigned_agent": "manager"}
    assert route_task(task) == "manager"
