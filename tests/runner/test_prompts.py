from runner.agents.prompts import build_system_prompt


def test_prompt_contains_role_id():
    prompt = build_system_prompt("manager")
    assert "manager" in prompt


def test_prompt_contains_display_name():
    prompt = build_system_prompt("manager")
    assert "Atlas" in prompt


def test_prompt_contains_purpose():
    prompt = build_system_prompt("heavy_worker")
    assert "Forge" in prompt
    assert "implementation" in prompt.lower()


def test_prompt_for_unknown_role_returns_generic():
    prompt = build_system_prompt("nonexistent_role")
    assert "nonexistent_role" in prompt


def test_all_defined_roles_build_without_error():
    roles = [
        "manager", "heavy_worker", "debug_worker", "content_worker",
        "media_worker", "audio_worker", "guard_worker", "budget_worker",
        "digital_product_worker", "marketing_worker",
    ]
    for role in roles:
        prompt = build_system_prompt(role)
        assert len(prompt) > 50, f"Prompt too short for {role}"
