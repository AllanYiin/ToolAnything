from tests.fixtures.sample_tools import registry, state_manager, workflow


def test_pipeline_execution_and_state():
    result = workflow(a=1, b=2, user_id="user1")
    assert result["sum"] == 3
    assert state_manager.get("user1")["last_sum"] == 3


def test_pipeline_registered_to_registry():
    exported = registry.to_openai_tools()
    assert any(t["function"]["name"] == "math.workflow" for t in exported)
