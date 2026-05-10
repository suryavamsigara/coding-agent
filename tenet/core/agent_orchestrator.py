from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tenet.core.memory import MemoryManager
from tenet.core.session_logger import SessionLogger, get_log_directory
from tenet.tools.context_ops import make_context_updater
from tenet.tools.executor import ToolExecutor
from tenet.tools.tool_schema import OPENAI_TOOLS_LIST
from tenet.ui.display import AgentDisplay

# ── File logger (debug only) ─────────────────────────────────────────────────
# Human-readable logs live in session_logger; this is for debug tracebacks only.

_handler = logging.FileHandler("agent_debug.log", mode="a", encoding="utf-8")
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-5s %(name)s | %(message)s", datefmt="%H:%M:%S",
))
log = logging.getLogger("tenet.agent")
log.setLevel(logging.DEBUG)
log.addHandler(_handler)
log.propagate = False

SYSTEM_PROMPT = (
    Path(__file__).parent.parent / "prompts" / "TENET.md"
).read_text(encoding="utf-8").strip()

MODEL_FLASH = "deepseek-v4-flash"
MODEL_PRO   = "deepseek-v4-pro"

# Context window limits

_MAX_STORED = 12_000   # chars kept in context per tool result


# Typed message containers

@dataclass
class ToolCallFunction:
    name: str
    arguments: str

@dataclass
class ToolCall:
    id: str
    type: str = "function"
    function: ToolCallFunction = field(default_factory=lambda: ToolCallFunction("", ""))

@dataclass
class AssistantMessage:
    """Typed assistant message - stored in memory, serialised for API."""
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    reasoning_content: str | None = None


# Stream accumulator

class _StreamAccumulator:
    """Accumulate SSE chunks into a complete AssistantMessage."""

    def __init__(self) -> None:
        self._content: list[str] = []
        self._reasoning: list[str] = []
        self._tcs: dict[int, dict[str, str]] = {}
        self.finish_reason: str | None = None

    def consume(self, chunk: Any) -> str | None:
        """Process one chunk. Returns text delta if any, None otherwise."""
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            return None

        if choice.finish_reason:
            self.finish_reason = choice.finish_reason

        delta = choice.delta

        # reasoning_content (thinking mode)
        rc = getattr(delta, "reasoning_content", None)
        if rc:
            self._reasoning.append(rc)

        # text content
        text = delta.content or ""
        if text:
            self._content.append(text)
            return text

        for tc in delta.tool_calls or []:
            buf = self._tcs.setdefault(tc.index, {"id": "", "name": "", "args": ""})
            buf["id"] = buf["id"] or (tc.id or "")
            if tc.function:
                buf["name"] += tc.function.name or ""
                buf["args"]  += tc.function.arguments or ""
        return None

    def to_message(self) -> AssistantMessage:
        tcs = None
        if self._tcs:
            tcs = [
                ToolCall(
                    id=self._tcs[i]["id"],
                    function=ToolCallFunction(
                        name=self._tcs[i]["name"],
                        arguments=self._tcs[i]["args"],
                    ),
                )
                for i in sorted(self._tcs)
            ]
        return AssistantMessage(
            content="".join(self._content) or None,
            tool_calls=tcs,
            reasoning_content="".join(self._reasoning) or None,
        )



class CodingAgent:
    def __init__(
        self,
        client: Any,
        model: str = MODEL_FLASH,
        thinking: bool = False,
        max_history_messages: int = 60,
        tools: list | None = None,
        log_dir=None,
    ) -> None:
        self.client = client
        self.model = model
        self.thinking = thinking
        self._tools = tools or OPENAI_TOOLS_LIST

        self.memory = MemoryManager(
            system_prompt=SYSTEM_PROMPT,
            max_history_messages=max_history_messages,
        )
        self.display = AgentDisplay()
        self.logger = SessionLogger(log_dir=log_dir or get_log_directory())

        context_updater = make_context_updater(self.memory)
        self.executor = ToolExecutor(
            context_updater=context_updater,
            file_read_tracker=self.memory.mark_file_read,
            display=self.display,
            logger=self.logger,
            # Live reference into memory - stays current as files are read/written
            known_files=self.memory.project.read_files,
        )

    # Public

    def reset_conversation(self) -> None:
        self.memory.clear()
        self.display.con.print(
            "[bold green]✓[/bold green] Conversation reset. Project context preserved."
        )

    def run_agent_loop(self, user_prompt: str, max_iterations: int = 60) -> str:
        log.info(
            "START prompt=%r model=%s thinking=%s",
            user_prompt[:80], self.model, self.thinking,
        )
        self.logger.log_session_start(user_prompt, self.model, self.thinking)

        self.memory.strip_reasoning_content()
        self.memory.add_user_message(user_prompt)

        total_tool_calls = 0

        for iteration in range(1, max_iterations + 1):
            msg = self._stream_turn(iteration, max_iterations)
            self.memory.add_assistant_message(msg)

            n_tools = len(msg.tool_calls or [])
            self.logger.log_llm_turn(iteration, self.memory.window_size(), n_tools)
            log.info("iter=%d window=%d tool_calls=%d", iteration, self.memory.window_size(), n_tools)

            if not msg.tool_calls:
                # Final turn - content is shown by show_final_answer in the CLI.
                log.info("DONE iter=%d", iteration)
                self.logger.log_session_end()
                return msg.content or ""

            # Persist any narration the model emitted alongside its tool calls.
            # Without this the commentary disappears when the Live panel closes.
            if msg.content and msg.content.strip():
                self.display.show_narration(msg.content)

            for tool_call in msg.tool_calls:
                self._dispatch_tool(tool_call)
                total_tool_calls += 1

        # Iteration cap
        self.display.show_iteration_warning(max_iterations)
        log.warning("MAX_ITER=%d reached", max_iterations)
        self.memory.strip_reasoning_content()
        self.memory.add_user_message(
            "You have reached the iteration limit. "
            "Summarise what was completed and what still needs to be done."
        )
        final = self._stream_turn(max_iterations + 1, max_iterations)
        self.logger.log_session_end()
        return final.content or f"[Stopped after {max_iterations} iterations.]"

    # Streaming LLM turn

    def _stream_turn(self, iteration: int, max_iter: int) -> AssistantMessage:
        kwargs = self._build_api_kwargs()
        try:
            stream = self.client.chat.completions.create(**kwargs)
            acc = _StreamAccumulator()

            with self.display.streaming_panel() as buf:
                for chunk in stream:
                    delta = acc.consume(chunk)
                    if delta:
                        buf.append(delta)

            return acc.to_message()
        except Exception as exc:
            log.error("LLM error: %s", exc, exc_info=True)
            self.logger.log_error("LLM call failed", exc)
            raise

    def _build_api_kwargs(self) -> dict:
        kwargs: dict = dict(
            model=self.model,
            messages=self.memory.get_messages(),
            tools=self._tools,
            stream=True,
        )
        if self.thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            kwargs["temperature"] = 0.0
            kwargs["tool_choice"] = "auto"
        return kwargs

    # Tool dispatch

    def _dispatch_tool(self, tool_call: ToolCall) -> None:
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            args = {}
            self.display.show_error(f"Invalid JSON args for tool '{name}'")

        raw_result = self.executor.execute(name, **args)

        # Truncate what goes into context to protect the window
        raw = (
            json.dumps(raw_result, indent=2, ensure_ascii=False)
            if isinstance(raw_result, (dict, list))
            else str(raw_result)
        )
        stored = raw[:_MAX_STORED]
        if len(raw) > _MAX_STORED:
            stored += f"\n[truncated — {len(raw):,} chars total]"

        self.memory.add_tool_observation(
            tool_call_id=tool_call.id,
            tool_name=name,
            content=stored,
        )
        log.debug("tool=%s stored=%d chars", name, len(stored))