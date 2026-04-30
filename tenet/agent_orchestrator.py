# my_agent/core/loop.py
import json
import logging
from openai.types.chat import ChatCompletionMessage

from tenet.client import client
from tenet.tools.executor import execute_tool
from tenet.tools.tool_schema import OPENAI_TOOLS_LIST

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a highly capable CLI coding agent. 
You can inspect directories, read, write, and execute code. 
Always use the provided tools to verify the state of the filesystem before and after making changes."""

class CodingAgent:
    def __init__(self, client, model="deepseek-chat", temperature=0.2):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.tools_list = OPENAI_TOOLS_LIST
        self.reset_conversation()
        self.logger = logging.getLogger(f"{__name__}.CodingAgent")

    def reset_conversation(self) -> None:
        self.message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    def get_agent_response(self) -> ChatCompletionMessage:
        """
        Sends the conversation history to OpenAI and returns the model's response.
        Includes the tool registry so the model knows what actions it can take.
        """
        self.logger.debug(f"Sending request with {len(self.message_history)} messages")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.message_history,
                tools=self.tools_list,
                tool_choice="auto",
                temperature=self.temperature,
            )
            self.logger.info(f"Received response with {len(response.choices[0].message.tool_calls or [])} tool calls")
            return response.choices[0].message
            
        except Exception as e:
            self.logger.error(f"API Error: {str(e)}", exc_info=True)
            raise e


    def run_agent_loop(self, user_prompt: str, max_iterations: int = 10) -> str:
        """
        The core Reason-Act-Observe loop. 
        Continues running until the LLM decides it has fully answered the user.
        """
        self.logger.info(f"Starting agent loop with prompt: {user_prompt[:100]}...")
        
        if self.message_history is None:
            self.message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
            
        self.message_history.append({"role": "user", "content": user_prompt})
        
        print("Thinking...")

        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            self.logger.info(f"Iteration {iteration} started")

            response_message = self.get_agent_response()
            
            self.message_history.append(response_message)
            
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name

                    self.logger.info(f"Executing tool: {tool_name}")
                    
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}
                        print(f"⚠️ Warning: LLM provided invalid JSON for tool {tool_name}")

                    print(f"🛠️  Executing: {tool_name}({', '.join(f'{k}={v}' for k, v in tool_args.items())})")
                    
                    observation = execute_tool(tool_name, **tool_args)
                    self.logger.debug(f"Tool output: {str(observation)[:200]}...")
                    
                    self.message_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": str(observation) 
                    })

                    logger.info(len(self.message_history))
                
            else:
                self.logger.info(f"Agent finished after {iteration} iterations")
                return response_message.content
            
        error_msg = f"Agent exceeded maximum iterations ({max_iterations}) without final answer"
        print(f"⚠️ {error_msg}")

agent = CodingAgent(client)

agent.run_agent_loop("")