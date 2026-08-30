from backend.langgraph.graph import _route_after_error_analysis
from backend.schemas.models import AgentState


def test_routes_to_success_when_success_flag_set(base_state):
    base_state.success = True
    assert _route_after_error_analysis(base_state) == "success"


def test_routes_to_retry_under_limit(base_state):
    base_state.success = False
    base_state.retry_count = 1
    base_state.max_retries = 5
    assert _route_after_error_analysis(base_state) == "retry"


def test_routes_to_max_retries_when_exceeded(base_state):
    base_state.success = False
    base_state.retry_count = 5
    base_state.max_retries = 5
    assert _route_after_error_analysis(base_state) == "max_retries"
