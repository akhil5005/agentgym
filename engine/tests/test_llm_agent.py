"""Tests for the LLM agent's tool-call plumbing, with a stubbed API client.

No API key and no network: a fake client returns scripted responses. This
verifies the part most likely to break — mapping tool calls to environment
actions, batching tool results correctly, and ending the episode cleanly when
the model stops asking for tools — without spending tokens.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentgym.models import UserFacingError


# --- stub API objects --------------------------------------------------------


class StubBlock:
    """Stands in for a content block in a response."""

    def __init__(self, type: str, **fields: Any) -> None:
        self.type = type
        for key, value in fields.items():
            setattr(self, key, value)


class StubUsage:
    def __init__(self, input_tokens: int = 10, output_tokens: int = 5) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0


class StubResponse:
    def __init__(self, content: list[StubBlock], stop_reason: str = "tool_use") -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.usage = StubUsage()


class StubMessages:
    """Captures requests and replays a scripted list of responses."""

    def __init__(self, responses: list[StubResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> StubResponse:
        # Snapshot the message list. The agent hands us its live list and keeps
        # appending to it after the call returns (harmless in production, since
        # the real SDK serialises immediately), so recording it by reference
        # would show us later turns instead of what this request contained.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        if not self._responses:
            # The agent asked for more than the test scripted: end the episode.
            return StubResponse([StubBlock("text", text="done")], stop_reason="end_turn")
        return self._responses.pop(0)


class StubClient:
    def __init__(self, responses: list[StubResponse]) -> None:
        self.messages = StubMessages(responses)


def tool_use(tool_id: str, name: str, payload: dict[str, Any] | None = None) -> StubBlock:
    return StubBlock("tool_use", id=tool_id, name=name, input=payload or {})


@pytest.fixture
def make_agent(monkeypatch):
    """Build an LLMAgent wired to a stub client with scripted responses."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-tests")
    monkeypatch.delenv("AGENTGYM_MODEL", raising=False)

    def factory(responses: list[StubResponse]):
        from agentgym.agents.llm import LLMAgent

        agent = LLMAgent()
        agent._client = StubClient(responses)  # noqa: SLF001 - test seam
        agent.start("Fix moving_average.", ["src/stats.py", "tests/test_visible.py"])
        return agent

    return factory


# --- construction ------------------------------------------------------------


def test_missing_api_key_raises_a_user_facing_error(monkeypatch) -> None:
    """The runner catches this type and prints one line, not a traceback."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from agentgym.agents.llm import LLMAgent, MissingAPIKeyError

    with pytest.raises(MissingAPIKeyError) as info:
        LLMAgent()

    assert isinstance(info.value, UserFacingError)
    message = str(info.value)
    assert "ANTHROPIC_API_KEY" in message
    # The message must tell the beginner what to do next.
    assert "export" in message or "$env:" in message
    assert "oracle" in message  # points at the agents that need no key


def test_a_blank_api_key_counts_as_missing(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    from agentgym.agents.llm import LLMAgent, MissingAPIKeyError

    with pytest.raises(MissingAPIKeyError):
        LLMAgent()


def test_default_model(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.delenv("AGENTGYM_MODEL", raising=False)
    from agentgym.agents.llm import DEFAULT_MODEL, LLMAgent

    assert LLMAgent().model == DEFAULT_MODEL == "claude-sonnet-5"


def test_model_comes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("AGENTGYM_MODEL", "claude-opus-5")
    from agentgym.agents.llm import LLMAgent

    assert LLMAgent().model == "claude-opus-5"


def test_an_explicit_model_wins_over_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("AGENTGYM_MODEL", "claude-opus-5")
    from agentgym.agents.llm import LLMAgent

    assert LLMAgent(model="claude-haiku-4-5").model == "claude-haiku-4-5"


# --- mapping tool calls to actions -------------------------------------------


def test_a_tool_call_becomes_an_action(make_agent) -> None:
    agent = make_agent([StubResponse([tool_use("t1", "list_files")])])
    assert agent.next_action("") == {"type": "list_files"}


def test_read_file_carries_its_path(make_agent) -> None:
    agent = make_agent(
        [StubResponse([tool_use("t1", "read_file", {"path": "src/stats.py"})])]
    )
    assert agent.next_action("") == {"type": "read_file", "path": "src/stats.py"}


def test_write_file_carries_path_and_content(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse(
                [tool_use("t1", "write_file", {"path": "src/a.py", "content": "x = 1\n"})]
            )
        ]
    )
    assert agent.next_action("") == {
        "type": "write_file",
        "path": "src/a.py",
        "content": "x = 1\n",
    }


def test_a_malformed_tool_call_still_becomes_an_action(make_agent) -> None:
    """A write with no content reaches the environment, which rejects it with an
    error observation the model can read and correct."""
    agent = make_agent([StubResponse([tool_use("t1", "write_file", {})])])
    assert agent.next_action("") == {"type": "write_file"}


def test_the_first_request_carries_the_task_briefing(make_agent) -> None:
    agent = make_agent([StubResponse([tool_use("t1", "list_files")])])
    agent.next_action("")

    request = agent._client.messages.requests[0]  # noqa: SLF001
    briefing = request["messages"][0]["content"]
    assert "Fix moving_average." in briefing
    assert "src/stats.py" in briefing
    assert request["model"] == agent.model
    assert len(request["tools"]) == 5


def test_the_system_prompt_does_not_mention_hidden_tests(make_agent) -> None:
    """Telling the model it is graded on hidden tests would invite gaming them."""
    agent = make_agent([StubResponse([tool_use("t1", "list_files")])])
    agent.next_action("")

    system = agent._client.messages.requests[0]["system"].lower()  # noqa: SLF001
    assert "hidden" not in system
    assert "reward" not in system


# --- feeding observations back ------------------------------------------------


def test_the_observation_comes_back_as_a_tool_result(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse([tool_use("t1", "list_files")]),
            StubResponse([tool_use("t2", "submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("src/stats.py\ntests/test_visible.py")

    second = agent._client.messages.requests[1]  # noqa: SLF001
    results = second["messages"][-1]
    assert results["role"] == "user"
    assert results["content"][0]["type"] == "tool_result"
    assert results["content"][0]["tool_use_id"] == "t1"
    assert "src/stats.py" in results["content"][0]["content"]


def test_the_assistant_turn_is_echoed_back_unchanged(make_agent) -> None:
    """Thinking blocks must survive the round trip, so we append the whole
    response rather than picking out the text."""
    thinking = StubBlock("thinking", thinking="let me look", signature="sig")
    call = tool_use("t1", "list_files")
    agent = make_agent(
        [
            StubResponse([thinking, call]),
            StubResponse([tool_use("t2", "submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("files")

    assistant = agent._client.messages.requests[1]["messages"][1]  # noqa: SLF001
    assert assistant["role"] == "assistant"
    assert assistant["content"] == [thinking, call]


def test_parallel_tool_calls_are_returned_one_at_a_time(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse(
                [
                    tool_use("t1", "read_file", {"path": "src/stats.py"}),
                    tool_use("t2", "read_file", {"path": "tests/test_visible.py"}),
                ]
            ),
            StubResponse([tool_use("t3", "submit")]),
        ]
    )

    assert agent.next_action("") == {"type": "read_file", "path": "src/stats.py"}
    assert agent.next_action("source") == {
        "type": "read_file",
        "path": "tests/test_visible.py",
    }
    # Only one request so far: the queued second call needed no new API call.
    assert len(agent._client.messages.requests) == 1  # noqa: SLF001

    assert agent.next_action("tests") == {"type": "submit"}


def test_parallel_tool_results_are_batched_into_one_user_message(make_agent) -> None:
    """Splitting results across messages teaches the model to stop making
    parallel calls, so they must arrive together."""
    agent = make_agent(
        [
            StubResponse([tool_use("t1", "list_files"), tool_use("t2", "run_tests")]),
            StubResponse([tool_use("t3", "submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("file listing")
    agent.next_action("test output")

    results = agent._client.messages.requests[1]["messages"][-1]  # noqa: SLF001
    assert results["role"] == "user"
    assert [block["tool_use_id"] for block in results["content"]] == ["t1", "t2"]
    assert len(results["content"]) == 2


# --- ending the episode ------------------------------------------------------


def test_text_with_no_tool_call_auto_submits(make_agent) -> None:
    agent = make_agent(
        [StubResponse([StubBlock("text", text="I think it is fine.")], stop_reason="end_turn")]
    )
    assert agent.next_action("") == {"type": "submit"}


def test_a_refusal_ends_the_episode_without_crashing(make_agent) -> None:
    """On a refusal there is nothing to read in content; submit and get graded."""
    agent = make_agent([StubResponse([], stop_reason="refusal")])
    assert agent.next_action("") == {"type": "submit"}


def test_hitting_max_tokens_with_no_tool_call_submits(make_agent) -> None:
    agent = make_agent(
        [StubResponse([StubBlock("text", text="truncated...")], stop_reason="max_tokens")]
    )
    assert agent.next_action("") == {"type": "submit"}


def test_no_further_api_calls_after_the_model_is_done(make_agent) -> None:
    agent = make_agent([StubResponse([StubBlock("text", text="bye")], stop_reason="end_turn")])
    agent.next_action("")
    agent.next_action("")
    agent.next_action("")
    # One request total: a finished conversation must not be retried every step.
    assert len(agent._client.messages.requests) == 1  # noqa: SLF001


# --- token usage -------------------------------------------------------------


def test_token_usage_accumulates_across_turns(make_agent) -> None:
    agent = make_agent(
        [
            StubResponse([tool_use("t1", "list_files")]),
            StubResponse([tool_use("t2", "run_tests")]),
            StubResponse([tool_use("t3", "submit")]),
        ]
    )
    agent.next_action("")
    agent.next_action("files")
    agent.next_action("tests")

    assert agent.token_usage["input_tokens"] == 30  # 3 calls x 10
    assert agent.token_usage["output_tokens"] == 15  # 3 calls x 5


def test_usage_summary_is_one_json_line(make_agent) -> None:
    agent = make_agent([StubResponse([tool_use("t1", "submit")])])
    agent.next_action("")
    summary = agent.usage_summary()
    assert "\n" not in summary
    assert "input_tokens" in summary


def test_missing_usage_fields_are_tolerated(make_agent) -> None:
    """The SDK may not return every cache field; that must not crash a run."""
    response = StubResponse([tool_use("t1", "submit")])
    response.usage = StubUsage()
    del response.usage.cache_read_input_tokens
    agent = make_agent([response])
    agent.next_action("")
    assert agent.token_usage["cache_read_input_tokens"] == 0


# --- the protocol ------------------------------------------------------------


def test_the_agent_satisfies_the_agent_protocol(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    from agentgym.agents.base import Agent
    from agentgym.agents.llm import LLMAgent

    agent = LLMAgent()
    assert isinstance(agent, Agent)
    assert agent.name == "llm"
    assert agent.model is not None  # unlike the scripted agents
