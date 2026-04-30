# my_agent/core/loop.py
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

base_path = Path(__file__).parent.parent
prompt_path = base_path / "prompts" / "TENET.md"

SYSTEM_PROMPT = prompt_path.read_text(encoding="utf-8").strip()

class CodingAgent:
    def __init__(self, client, model="deepseek-chat", temperature=0.2):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.tools_list = OPENAI_TOOLS_LIST
        self.logger = logging.getLogger(f"{__name__}.CodingAgent")

        self.memory = MemoryManager(system_prompt=SYSTEM_PROMPT, max_history_messages=20)

    def reset_conversation(self) -> None:
        self.memory.clear()
        self.logger.info("Conversation memory reset.")
    
    def get_agent_response(self) -> ChatCompletionMessage:
        """
        Sends the conversation history to OpenAI and returns the model's response.
        Includes the tool registry so the model knows what actions it can take.
        """
        current_history = self.memory.get_messages()

        self.logger.debug(f"Sending request with {len(current_history)} messages"  )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=current_history,
                tools=self.tools_list,
                tool_choice="auto",
                temperature=self.temperature,
            )
            self.logger.info(f"Received response with {len(response.choices[0].message.tool_calls or [])} tool calls")
            return response.choices[0].message
            
        except Exception as e:
            self.logger.error(f"API Error: {str(e)}", exc_info=True)
            raise e


    def run_agent_loop(self, user_prompt: str, max_iterations: int = 5) -> str:
        """
        The core Reason-Act-Observe loop. 
        Continues running until the LLM decides it has fully answered the user.
        """
        self.logger.info(f"Starting agent loop with prompt: {user_prompt[:100]}...")

        self.memory.add_user_message(user_prompt)

        iteration = 0
        response_message = ""

        while iteration < max_iterations:
            iteration += 1
            self.logger.info(f"Iteration {iteration} started")

            response_message = self.get_agent_response()
            self.memory.add_assistant_message(response_message)
                        
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name

                    self.logger.info(f"Executing tool: {tool_name}")
                    
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}
                        print(f"⚠️ Warning: LLM provided invalid JSON for tool {tool_name}")
                    
                    observation = execute_tool(tool_name, **tool_args)
                    self.logger.debug(f"Tool output: {str(observation)[:200]}...")
                    
                    self.memory.add_tool_observartion(
                        tool_call_id=tool_call.id,
                        tool_name=tool_name,
                        content=str(observation) 
                    )

                    self.logger.info(len(self.memory.get_messages()))
                
            else:
                self.logger.info(f"Agent finished after {iteration} iterations")
                return response_message.content
            
        error_msg = f"Agent exceeded maximum iterations ({max_iterations}) without final answer"
        return error_msg 
