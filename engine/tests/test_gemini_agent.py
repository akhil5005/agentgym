"""Tests for the Gemini agent's function-calling plumbing, with a stub client.

No API key, no network, no quota spent. This covers the part most likely to
break — mapping function calls to environment actions, batching function
responses correctly, pacing and retrying rate limits, and ending the episode
cleanly when the model stops calling functions.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentgym.models import UserFacingError

pytest.importorskip("google.genai", reason="google-genai is an optional extra")

from google.genai import types  # noqa: E402


# --- stub API objects --------------------------------------------------------


class StubUsage:
    def __init__(self) -> None:
        self.prompt_token_count = 100
        self.candidates_token_count = 20
        self.thoughts_token_count = 5
        self.total_token_count = 125


class StubCandidate:
    def __init__(self, content: Any, finish_reason: str = "STOP") -> None:
        self.content = content
        self.finish_reason = types.FinishReason(finish_reason)


class StubResponse:
    """Mimics GenerateContentResponse closely enough for the agent."""

    def __init__(self, parts: list[Any], finish_reason: str = "STOP") -> None:
        content = types.Content(role="model", parts=parts)
        self.candidates = [StubCandidate(content, finish_reason)]
        self.usage_metadata = StubUsage()

    @property
    def function_calls(self) -> list[Any]:
        calls = []
        for part in self.candidates[0].content.parts or []:
            if part.function_call is not None:
                calls.append(part.function_call)
        return calls


class StubModels:
    """Replays scripted responses and records what was sent."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        # Snapshot the history: the agent keeps appending to its live list.
        self.requests.append({**kwargs, "contents": list(kwargs["contents"])})
        if not self._responses:
            return StubResponse([types.Part(text="done")])
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class StubClient:
    def __init__(self, responses: list[Any]) -> None:
        self.models = StubModels(responses)


def call_part(name: str, args: dict[str, Any] | None = None, call_id: str | None = None):
    """A model turn containing one function call."""
    call = types.FunctionCall(name=name, args=args or {})
    if call_id:
        call.id = call_id
    return types.Part(function_call=call)


@pytest.fixture
def make_agent(monkeypatch):
    """Build a GeminiAgent wired to a stub client, with pacing turned off."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
    monkeypatch.delenv("AGENTGYM_GEMINI_MODEL", raising=False)
    # Pacing would make the suite sleep for real.
    monkeypatch.setenv("AGENTGYM_GEMINI_INTERVAL", "0")

    def factory(responses: list[Any]):
        from agentgym.agents.gemini import GeminiAgent

        agent = GeminiAgent()
        agent._client = StubClient(responses)  # noqa: SLF001 - test seam
        agent.start("Fix moving_average.", ["src/stats.py", "tests/test_visible.py"])
        return agent

    return factory


# --- construction ------------------------------------------------------------


def test_missing_api_key_raises_a_user_facing_error(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from agentgym.agents.gemini import GeminiAgent, MissingAPIKeyError

    with pytest.raises(MissingAPIKeyError) as info:
        GeminiAgent()

    assert isinstance(info.value, UserFacingError)
    message = str(info.value)
    assert "GEMINI_API_KEY" in message
    assert "aistudio.google.com" in message  # tells you where to get one
    assert "oracle" in message  # points at the agents needing no key


def test_google_api_key_is_accepted_as_a_fallback(monkeypatch) -> None:
    """The SDK's own env var name works too, so a key set either way is found."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "fallback-key")
    from agentgym.agents.gemini import GeminiAgent

    assert GeminiAgent().name == "gemini"


def test_a_blank_key_counts_as_missing(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from agentgym.agents.gemini import GeminiAgent, MissingAPIKeyError

    with pytest.raises(MissingAPIKeyError):
        GeminiAgent()


def test_default_model_is_a_flash_model(monkeypatch) -> None:
    """Free-tier availability is the constraint; Flash is what meets it."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.delenv("AGENTGYM_GEMINI_MODEL", raising=False)
    from agentgym.agents.gemini import DEFAULT_MODEL, GeminiAgent

    assert "flash" in DEFAULT_MODEL
    assert GeminiAgent().model == DEFAULT_MODEL


def test_model_comes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("AGENTGYM_GEMINI_MODEL", "gemini-2.0-flash")
    from agentgym.agents.gemini import GeminiAgent

    assert GeminiAgent().model == "gemini-2.0-flash"


def test_automatic_function_calling_is_disabled(monkeypatch) -> None:
    """The environment runs the actions. If the SDK ran them it would bypass
    the guard, the step counter and the step limit."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    from agentgym.agents.gemini import GeminiAgent

    config = GeminiAgent()._config  # noqa: SLF001
    assert config.automatic_function_calling.disable is True


def test_all_five_actions_are_declared(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    from agentgym.agents.gemini import GeminiAgent

    config = GeminiAgent()._config  # noqa: SLF001
    names = {d.name for d in config.tools[0].function_declarations}
    assert names == {"list_files", "read_file", "write_file", "run_tests", "submit"}


def test_the_system_prompt_does_not_mention_hidden_tests(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    from agentgym.agents.gemini import GeminiAgent

    system = GeminiAgent()._config.system_instruction.lower()  # noqa: SLF001
    assert "hidden" not in system
    assert "reward" not in system


# --- mapping function calls to actions ---------------------------------------


def test_a_function_call_becomes_an_action(make_agent) -> None:
    agent = make_agent([StubResponse([call_part("list_files")])])
    assert agent.next_action("") == {"type": "list_files"}


def test_read_file_carries_its_path(make_agent) -> None:
    agent = make_agent([StubResponse([call_part("read_file", {"path": "src/stats.py"})])])
    assert agent.next_action("") == {"type": "read_file", "path": "src/stats.py"}


def test_write_file_carries_path_and_content(make_agent) -> None:
    agent = make_agent(
        [StubResponse([call_part("write_file", {"path": "src/a.py", "content": "x = 1\n"})])]
    )
    assert agent.next_action("") == {
        "type": "write_file",
        "path": "src/a.py",
        "content": "x = 1\n",
    }


def test_a_malformed_call_still_becomes_an_action(make_agent) -> None:
    """The environment rejects it with an error the model can read and fix."""
    agent = make_agent([StubResponse([call_part("write_file", {})])])
    assert agent.next_action("") == {"type": "write_file"}


def test_the_first_request_carries_the_briefing(make_agent) -> None:
    agent = make_agent([StubResponse([call_part("list_files")])])
    agent.next_action("")

    request = agent._client.models.requests[0]  # noqa: SLF001
    briefing = request["contents"][0].parts[0].text
    assert "Fix moving_average." in briefing
    assert "src/stats.py" in briefing
    assert request["model"] == agent.model


# --- feeding observations back ------------------------------------------------


def test_the_observation_comes_back_as_a_function_response(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse([call_part("list_files")]),
            StubResponse([call_part("submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("src/stats.py\ntests/test_visible.py")

    contents = agent._client.models.requests[1]["contents"]  # noqa: SLF001
    last = contents[-1]
    assert last.role == "user"
    response = last.parts[0].function_response
    assert response.name == "list_files"
    assert "src/stats.py" in response.response["result"]


def test_the_model_turn_is_echoed_back(make_agent) -> None:
    """The next request must carry the calls it is answering."""
    agent = make_agent(
        [StubResponse([call_part("list_files")]), StubResponse([call_part("submit")])]
    )
    agent.next_action("")
    agent.next_action("files")

    contents = agent._client.models.requests[1]["contents"]  # noqa: SLF001
    assert contents[1].role == "model"
    assert contents[1].parts[0].function_call.name == "list_files"


def test_a_call_id_is_echoed_on_the_response(make_agent) -> None:
    """Gemini matches a response to its call by id when several run at once."""
    agent = make_agent(
        [
            StubResponse([call_part("list_files", call_id="call-1")]),
            StubResponse([call_part("submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("files")

    contents = agent._client.models.requests[1]["contents"]  # noqa: SLF001
    assert contents[-1].parts[0].function_response.id == "call-1"


def test_parallel_calls_are_returned_one_at_a_time(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse(
                [
                    call_part("read_file", {"path": "src/stats.py"}),
                    call_part("read_file", {"path": "tests/test_visible.py"}),
                ]
            ),
            StubResponse([call_part("submit")]),
        ]
    )

    assert agent.next_action("") == {"type": "read_file", "path": "src/stats.py"}
    assert agent.next_action("source") == {
        "type": "read_file",
        "path": "tests/test_visible.py",
    }
    # The queued second call needed no extra API call.
    assert len(agent._client.models.requests) == 1  # noqa: SLF001


def test_parallel_responses_are_batched_into_one_user_turn(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse([call_part("list_files"), call_part("run_tests")]),
            StubResponse([call_part("submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("file listing")
    agent.next_action("test output")

    last = agent._client.models.requests[1]["contents"][-1]  # noqa: SLF001
    assert last.role == "user"
    assert len(last.parts) == 2
    assert [p.function_response.name for p in last.parts] == ["list_files", "run_tests"]


# --- ending the episode ------------------------------------------------------


def test_text_with_no_call_auto_submits(make_agent) -> None:
    agent = make_agent([StubResponse([types.Part(text="Looks fine to me.")])])
    assert agent.next_action("") == {"type": "submit"}


def test_a_safety_stop_ends_the_episode(make_agent) -> None:
    agent = make_agent([StubResponse([types.Part(text="")], finish_reason="SAFETY")])
    assert agent.next_action("") == {"type": "submit"}


def test_a_malformed_function_call_finish_reason_ends_the_episode(make_agent) -> None:
    agent = make_agent(
        [StubResponse([types.Part(text="")], finish_reason="MALFORMED_FUNCTION_CALL")]
    )
    assert agent.next_action("") == {"type": "submit"}


def test_no_further_api_calls_once_the_model_is_done(make_agent) -> None:
    agent = make_agent([StubResponse([types.Part(text="bye")])])
    agent.next_action("")
    agent.next_action("")
    agent.next_action("")
    assert len(agent._client.models.requests) == 1  # noqa: SLF001


# --- rate limits and retries --------------------------------------------------


def _client_error(code: int, message: str):
    """Build a google-genai ClientError without touching the network."""
    from google.genai import errors

    return errors.ClientError(code, {"error": {"message": message, "code": code}})


def test_a_per_minute_rate_limit_is_retried(make_agent, monkeypatch) -> None:
    import agentgym.agents.gemini as gemini_module

    monkeypatch.setattr(gemini_module.time, "sleep", lambda _seconds: None)
    agent = make_agent(
        [
            _client_error(429, "Quota exceeded for quota metric 'RequestsPerMinute'"),
            StubResponse([call_part("list_files")]),
        ]
    )
    # Retried transparently; the caller just gets the action.
    assert agent.next_action("") == {"type": "list_files"}
    assert agent.api_calls == 2


def test_a_daily_quota_stop_is_fatal(make_agent, monkeypatch) -> None:
    """The instruction is to stop rather than move to a paid model."""
    import agentgym.agents.gemini as gemini_module
    from agentgym.agents.gemini import QuotaExhaustedError

    monkeypatch.setattr(gemini_module.time, "sleep", lambda _seconds: None)
    agent = make_agent(
        [_client_error(429, "Quota exceeded: generate_requests_per_model_per_day")]
    )
    with pytest.raises(QuotaExhaustedError) as info:
        agent.next_action("")
    assert "free-tier quota is exhausted" in str(info.value)
    assert isinstance(info.value, UserFacingError)


def test_a_bad_request_is_not_retried(make_agent, monkeypatch) -> None:
    """A 400 is our mistake; retrying sends the same bad request again."""
    import agentgym.agents.gemini as gemini_module
    from google.genai import errors

    monkeypatch.setattr(gemini_module.time, "sleep", lambda _seconds: None)
    agent = make_agent([_client_error(400, "Invalid function declaration")])
    with pytest.raises(errors.ClientError):
        agent.next_action("")
    assert agent.api_calls == 1


def test_a_server_error_is_retried(make_agent, monkeypatch) -> None:
    import agentgym.agents.gemini as gemini_module
    from google.genai import errors

    monkeypatch.setattr(gemini_module.time, "sleep", lambda _seconds: None)
    agent = make_agent(
        [
            errors.ServerError(503, {"error": {"message": "overloaded", "code": 503}}),
            StubResponse([call_part("submit")]),
        ]
    )
    assert agent.next_action("") == {"type": "submit"}
    assert agent.api_calls == 2


def test_giving_up_after_repeated_failures_is_user_facing(make_agent, monkeypatch) -> None:
    import agentgym.agents.gemini as gemini_module
    from agentgym.agents.gemini import MAX_ATTEMPTS
    from google.genai import errors

    monkeypatch.setattr(gemini_module.time, "sleep", lambda _seconds: None)
    agent = make_agent(
        [errors.ServerError(503, {"error": {"message": "nope", "code": 503}})]
        * MAX_ATTEMPTS
    )
    with pytest.raises(UserFacingError, match="did not respond"):
        agent.next_action("")
    assert agent.api_calls == MAX_ATTEMPTS


def test_quota_classifier_tells_per_minute_from_per_day() -> None:
    from agentgym.agents.gemini import _is_quota_exhausted

    per_minute = _client_error(429, "quota metric 'Requests per minute' exceeded")
    per_day = _client_error(429, "limit: generate_requests_per_model_per_day")
    assert _is_quota_exhausted(per_minute) is False
    assert _is_quota_exhausted(per_day) is True


# --- token usage -------------------------------------------------------------


def test_token_usage_accumulates(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse([call_part("list_files")]),
            StubResponse([call_part("run_tests")]),
            StubResponse([call_part("submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("files")
    agent.next_action("tests")

    assert agent.token_usage["prompt_tokens"] == 300  # 3 calls x 100
    assert agent.token_usage["total_tokens"] == 375
    assert agent.api_calls == 3


def test_usage_summary_is_one_json_line(make_agent) -> None:
    agent = make_agent([StubResponse([call_part("submit")])])
    agent.next_action("")
    summary = agent.usage_summary()
    assert "\n" not in summary
    assert "total_tokens" in summary and "api_calls" in summary


# --- the protocol and the runner ---------------------------------------------


def test_the_agent_satisfies_the_agent_protocol(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    from agentgym.agents.base import Agent
    from agentgym.agents.gemini import GeminiAgent

    agent = GeminiAgent()
    assert isinstance(agent, Agent)
    assert agent.name == "gemini"
    assert agent.model is not None


@pytest.mark.parametrize("cli_name", ["gemini", "llm"])
def test_the_runner_builds_gemini_for_both_names(monkeypatch, cli_name: str) -> None:
    """`llm` is an alias for Gemini, so older commands keep working."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    from agentgym.agents.gemini import GeminiAgent
    from agentgym.runner import _build_agent
    from agentgym.tasks import list_task_ids, load_task, tasks_dir

    task = load_task(list_task_ids(tasks_dir())[0], tasks_dir())
    assert isinstance(_build_agent(cli_name, task), GeminiAgent)


def test_gemini_is_the_declared_default_llm() -> None:
    from agentgym.runner import DEFAULT_LLM, LLM_AGENTS

    assert DEFAULT_LLM == "gemini"
    assert "gemini" in LLM_AGENTS and "llm" in LLM_AGENTS
