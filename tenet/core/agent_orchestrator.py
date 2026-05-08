import json
import logging
from pathlib import Path
from openai.types.chat import ChatCompletionMessage

from tenet.tools.executor import execute_tool
from tenet.tools.tool_schema import OPENAI_TOOLS_LIST
from tenet.core.memory import MemoryManager

logging.basicConfig(
    filename="agent_debug.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

base_path = Path(__file__).parent.parent
prompt_path = base_path / "prompts" / "TENET.md"
SYSTEM_PROMPT = prompt_path.read_text(encoding="utf-8").strip()

MAX_TOOL_OUTPUT_DISPLAY = 2000   # chars shown in terminal per tool result
MAX_TOOL_OUTPUT_MEMORY = 20_000  # chars stored in context per tool result


class CodingAgent:
    def __init__(
        self,
        client,
        model: str = "deepseek-chat",
        temperature: float = 0.2,
        max_history_messages: int = 60,
    ):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.tools_list = OPENAI_TOOLS_LIST
        self.logger = logging.getLogger(f"{__name__}.CodingAgent")

        self.memory = MemoryManager(
            system_prompt=SYSTEM_PROMPT,
            max_history_messages=max_history_messages,
        )

    def reset_conversation(self) -> None:
        """Clear all conversation history (keeps system prompt)."""
        self.memory.clear()
        self.logger.info("Conversation memory reset.")
        print("[tenet] Conversation reset.")

    def run_agent_loop(
        self,
        user_prompt: str,
        max_iterations: int = 60,
        stream_thoughts: bool = True,
    ) -> str:
        """
        Core Reason-Act-Observe loop.

        1. Send the conversation to the LLM.
        2. If the LLM calls tools, execute them and feed results back.
        3. Repeat until the LLM produces a plain text response (no tool calls).

        Args:
            user_prompt: The user's request.
            max_iterations: Number of LLM -> tool -> observe cycles.
            stream_thoughts: If True, print tool names + results to stdout in real-time.

        Returns:
            The agent's final text answer.
        """
        self.logger.info(f"Starting agent loop | prompt: {user_prompt[:120]}...")
        self.memory.add_user_message(user_prompt)

        for iteration in range(1, max_iterations + 1):
            self.logger.info(f"Iteration {iteration}/{max_iterations}")

            response_message = self._get_agent_response()
            self.memory.add_assistant_message(response_message)

            if not response_message.tool_calls:
                self.logger.info(f"Agent finished at iteration {iteration}")
                return response_message.content or ""

            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name

                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                    print(f"  Warning: invalid JSON args for '{tool_name}', using empty dict")

                if stream_thoughts:
                    self._print_tool_call(tool_name, tool_args)

                # Execute
                observation = execute_tool(tool_name, **tool_args)

                # Serialise for display + memory
                if isinstance(observation, (dict, list)):
                    raw_output = json.dumps(observation, indent=2, ensure_ascii=False)
                else:
                    raw_output = str(observation)

                if stream_thoughts:
                    self._print_tool_result(tool_name, raw_output)

                # Truncate before storing to avoid ballooning the context
                memory_output = raw_output[:MAX_TOOL_OUTPUT_MEMORY]
                if len(raw_output) > MAX_TOOL_OUTPUT_MEMORY:
                    memory_output += f"\n... [truncated — {len(raw_output)} chars total]"

                self.memory.add_tool_observation(
                    tool_call_id=tool_call.id,
                    tool_name=tool_name,
                    content=memory_output,
                )

                self.logger.info(
                    f"Tool '{tool_name}' → {len(raw_output)} chars output | "
                    f"history size: {len(self.memory.get_messages())}"
                )

        warn = f"[tenet] Reached max iterations ({max_iterations}). Requesting final summary..."
        print(warn)
        self.logger.warning(warn)

        # Ask the model for a final answer with what it has
        self.memory.add_user_message(
            "You've used many tool calls. Please provide your best final answer now "
            "based on everything you've learned so far."
        )
        final_response = self._get_agent_response()
        return final_response.content or f"[Agent exceeded {max_iterations} iterations without completing.]"

    # ---------------------------------------------------------
    #  Internal helpers
    # ---------------------------------------------------------

    def _get_agent_response(self) -> ChatCompletionMessage:
        """Send the current conversation to the LLM and return its message."""
        current_history = self.memory.get_messages()
        self.logger.debug(f"Sending {len(current_history)} messages to {self.model}")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=current_history,
                tools=self.tools_list,
                tool_choice="auto",
                temperature=self.temperature,
            )
            n_calls = len(response.choices[0].message.tool_calls or [])
            self.logger.info(f"LLM response: {n_calls} tool call(s)")
            return response.choices[0].message
        except Exception as e:
            self.logger.error(f"API error: {e}", exc_info=True)
            raise

    @staticmethod
    def _print_tool_call(tool_name: str, args: dict) -> None:
        """Pretty-print a tool invocation to stdout."""
        args_preview = json.dumps(args, ensure_ascii=False)
        if len(args_preview) > 300:
            args_preview = args_preview[:300] + "..."
        print(f"\n  🔧 {tool_name}({args_preview})")

    @staticmethod
    def _print_tool_result(tool_name: str, output: str) -> None:
        """Pretty-print a tool result to stdout (truncated for readability)."""
        preview = output[:MAX_TOOL_OUTPUT_DISPLAY]
        if len(output) > MAX_TOOL_OUTPUT_DISPLAY:
            preview += f"\n  ... [{len(output)} chars total]"
        # Indent each line
        indented = "\n".join("     " + line for line in preview.splitlines())
        print(f"  ↳  {indented.lstrip()}")