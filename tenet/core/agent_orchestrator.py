import json
import logging
from pathlib import Path
from openai.types.chat import ChatCompletionMessage
 
from tenet.tools.executor import execute_tool
from tenet.tools.context_ops import bind_memory
from tenet.tools.tool_schema import OPENAI_TOOLS_LIST
from tenet.core.memory import MemoryManager
  
_file_handler = logging.FileHandler("agent_debug.log", mode="a", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-5s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
))
 
log = logging.getLogger("tenet.agent")
log.setLevel(logging.DEBUG)
log.addHandler(_file_handler)
log.propagate = False

base_path = Path(__file__).parent.parent
prompt_path = base_path / "prompts" / "TENET.md"
SYSTEM_PROMPT = prompt_path.read_text(encoding="utf-8").strip()

MAX_TOOL_OUTPUT_IN_CONTEXT = 12_000
 
MAX_TOOL_OUTPUT_DISPLAY = 1_500
 
 
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
        self.max_history_messages = max_history_messages
        self.tools_list = OPENAI_TOOLS_LIST
 
        self.memory = MemoryManager(
            system_prompt=SYSTEM_PROMPT,
            max_history_messages=max_history_messages,
        )
        bind_memory(self.memory)
  
    def reset_conversation(self) -> None:
        self.memory.clear()
        print("[tenet] Conversation reset.")
 
    def run_agent_loop(self, user_prompt: str, max_iterations: int = 50) -> str:
        log.info(f"START prompt={user_prompt[:80]!r} max_iter={max_iterations} window_limit={self.max_history_messages}")
        self.memory.add_user_message(user_prompt)
 
        for iteration in range(1, max_iterations + 1):
            response = self._call_llm(iteration, max_iterations)
            self.memory.add_assistant_message(response)
 
            if not response.tool_calls:
                log.info(f"DONE  iter={iteration} window={self.memory.window_size()}")
                return response.content or ""
 
            for tool_call in response.tool_calls:
                self._execute_tool_call(tool_call)
 
        log.warning(f"MAX_ITER reached ({max_iterations})")
        self.memory.add_user_message(
            "You've reached the iteration limit. Give your best final answer based on what you've done so far."
        )
        response = self._call_llm(max_iterations + 1, max_iterations)
        return response.content or f"[Reached {max_iterations} iterations without finishing.]"
 
 
    def _call_llm(self, iteration: int, max_iterations: int) -> ChatCompletionMessage:
        window = self.memory.window_size()
        log.debug(f"iter={iteration}/{max_iterations} window={window} → calling LLM")
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self.memory.get_messages(),
                tools=self.tools_list,
                tool_choice="auto",
                temperature=self.temperature,
            )
            n = len(resp.choices[0].message.tool_calls or [])
            log.info(f"iter={iteration} window={window} tool_calls={n}")
            return resp.choices[0].message
        except Exception as e:
            log.error(f"LLM error: {e}", exc_info=True)
            raise
 
    def _execute_tool_call(self, tool_call) -> None:
        tool_name = tool_call.function.name
 
        try:
            tool_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            tool_args = {}
            print(f"  ⚠  Bad JSON args for {tool_name}")
 
        # Print call
        args_str = json.dumps(tool_args, ensure_ascii=False)
        if len(args_str) > 200:
            args_str = args_str[:200] + "…"
        print(f"\n  🔧 {tool_name}  {args_str}")
 
        # Execute
        result = execute_tool(tool_name, **tool_args)
 
        # Serialise
        raw = json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
 
        # Display (truncated)
        display = raw[:MAX_TOOL_OUTPUT_DISPLAY]
        if len(raw) > MAX_TOOL_OUTPUT_DISPLAY:
            display += f"\n  … [{len(raw):,} chars total]"
        for line in display.splitlines():
            print(f"     {line}")
 
        # Store in context (truncated at a higher limit)
        stored = raw[:MAX_TOOL_OUTPUT_IN_CONTEXT]
        if len(raw) > MAX_TOOL_OUTPUT_IN_CONTEXT:
            stored += f"\n[truncated — {len(raw):,} chars total]"
 
        self.memory.add_tool_observation(
            tool_call_id=tool_call.id,
            tool_name=tool_name,
            content=stored,
        )
 
        log.info(f"  tool={tool_name} output={len(raw):,}chars window={self.memory.window_size()}")