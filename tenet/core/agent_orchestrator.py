from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from tenet.core.memory import MemoryManager
from tenet.tools.context_ops import make_context_updater
from tenet.tools.executor import ToolExecutor
from tenet.tools.tool_schema import OPENAI_TOOLS_LIST


_handler = logging.FileHandler("agent_debug.log", mode="a", encoding="utf-8")
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-5s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
))
log = logging.getLogger("tenet.agent")
log.setLevel(logging.DEBUG)
log.addHandler(_handler)
log.propagate = False

base_path = Path(__file__).parent.parent
prompt_path = base_path / "prompts" / "TENET.md"
SYSTEM_PROMPT = prompt_path.read_text(encoding="utf-8").strip()

MODEL_FLASH   = "deepseek-v4-flash"
MODEL_PRO     = "deepseek-v4-pro"

_MAX_DISPLAY = 1_500
_MAX_STORED  = 12_000

console = Console()


# Typed message containers (avoid raw SDK object dependencies)

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
        self._tool_calls: dict[int, dict[str, str]] = {}
        self.finish_reason: str | None = None

    def consume(self, chunk) -> str | None:
        """
        Process one chunk. Returns text delta if any (for live display),
        None otherwise.
        """
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

        # tool call chunks
        for tc_chunk in delta.tool_calls or []:
            idx = tc_chunk.index
            if idx not in self._tool_calls:
                self._tool_calls[idx] = {"id": "", "name": "", "args": ""}
            buf = self._tool_calls[idx]
            buf["id"] = buf["id"] or (tc_chunk.id or "")
            if tc_chunk.function:
                buf["name"] += tc_chunk.function.name or ""
                buf["args"] += tc_chunk.function.arguments or ""

        return None

    def to_message(self) -> AssistantMessage:
        tool_calls = None
        if self._tool_calls:
            tool_calls = [
                ToolCall(
                    id=buf["id"],
                    function=ToolCallFunction(name=buf["name"], arguments=buf["args"]),
                )
                for buf in (self._tool_calls[i] for i in sorted(self._tool_calls))
            ]
        return AssistantMessage(
            content="".join(self._content) or None,
            tool_calls=tool_calls,
            reasoning_content="".join(self._reasoning) or None,
        )



class CodingAgent:
    def __init__(
        self,
        client,
        model: str = MODEL_FLASH,
        thinking: bool = False,
        max_history_messages: int = 60,
        tools: list | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.thinking = thinking
        self._tools = tools or OPENAI_TOOLS_LIST

        self.memory = MemoryManager(
            system_prompt=SYSTEM_PROMPT,
            max_history_messages=max_history_messages,
        )

        # Wire update_project_context to this agent's memory
        updater = make_context_updater(self.memory)
        self.executor = ToolExecutor(context_updater=updater)

    def reset_conversation(self) -> None:
        self.memory.clear()
        console.print("[bold green]✓[/bold green] Conversation reset. Project context preserved.")

    def run_agent_loop(self, user_prompt: str, max_iterations: int = 60) -> str:
        log.info(
            "START prompt=%r model=%s thinking=%s",
            user_prompt[:80], self.model, self.thinking,
        )

        self.memory.strip_reasoning_content()
        self.memory.add_user_message(user_prompt)

        for iteration in range(1, max_iterations + 1):
            msg = self._stream_llm(iteration, max_iterations)
            self.memory.add_assistant_message(msg)

            if not msg.tool_calls:
                log.info("DONE iter=%d window=%d", iteration, self.memory.window_size())
                return msg.content or ""

            for tool_call in msg.tool_calls:
                self._run_tool(tool_call)

        # Iteration cap
        log.warning("MAX_ITER=%d reached", max_iterations)
        self.memory.strip_reasoning_content()
        self.memory.add_user_message(
            "You have reached the iteration limit. "
            "Summarise what was completed and what still needs to be done."
        )
        final = self._stream_llm(max_iterations + 1, max_iterations)
        return final.content or f"[Stopped after {max_iterations} iterations.]"


    def _stream_llm(self, iteration: int, max_iterations: int) -> AssistantMessage:
        window = self.memory.window_size()
        log.debug("iter=%d/%d window=%d", iteration, max_iterations, window)

        kwargs = self._build_kwargs(stream=True)

        try:
            stream = self.client.chat.completions.create(**kwargs)
            acc = _StreamAccumulator()
            buf: list[str] = []

            with Live(console=console, refresh_per_second=15) as live:
                for chunk in stream:
                    delta = acc.consume(chunk)
                    if delta:
                        buf.append(delta)
                        live.update(Markdown("".join(buf)))

            msg = acc.to_message()
            n_tools = len(msg.tool_calls or [])
            log.info("iter=%d window=%d tool_calls=%d", iteration, window, n_tools)
            return msg

        except Exception as exc:
            log.error("LLM error: %s", exc, exc_info=True)
            raise

    def _build_kwargs(self, stream: bool = False) -> dict:
        kwargs: dict = dict(
            model=self.model,
            messages=self.memory.get_messages(),
            tools=self._tools,
            stream=stream,
        )
        if self.thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            kwargs["temperature"] = 0.0
            kwargs["tool_choice"] = "auto"
        return kwargs

    # Tool execution

    def _run_tool(self, tool_call: ToolCall) -> None:
        name = tool_call.function.name

        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            args = {}
            console.print(f"  [bold yellow]Error[/bold yellow]  invalid JSON args for [cyan]{name}[/cyan]")

        preview = json.dumps(args, ensure_ascii=False)
        if len(preview) > 200:
            preview = preview[:200] + "…"
        console.print(f"\n  [bold cyan]🔧 {name}[/bold cyan]  [dim]{preview}[/dim]")

        result = self.executor.execute(name, **args)

        raw = (
            json.dumps(result, indent=2, ensure_ascii=False)
            if isinstance(result, (dict, list))
            else str(result)
        )

        display = raw[:_MAX_DISPLAY]
        if len(raw) > _MAX_DISPLAY:
            display += f"\n  … [{len(raw):,} chars total]"
        for line in display.splitlines():
            console.print(f"     [dim]{line}[/dim]")

        stored = raw[:_MAX_STORED]
        if len(raw) > _MAX_STORED:
            stored += f"\n[truncated — {len(raw):,} chars total]"

        self.memory.add_tool_observation(
            tool_call_id=tool_call.id,
            tool_name=name,
            content=stored,
        )
        log.info("  tool=%s out=%d chars window=%d", name, len(raw), self.memory.window_size())
        