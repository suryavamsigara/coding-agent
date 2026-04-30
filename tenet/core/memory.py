import json
from typing import Any

class MemoryManager:
    def __init__(self, system_prompt: str, max_history_messages: int = 20):
        """
        Initializes the memory with a system prompt and a limit on how many messages to remember to prevent blowing up the context window.
        """
        self.system_prompt = system_prompt
        self.max_history_messages = max_history_messages
        self.messages = list[dict[str, Any]]

        self.clear()

    def clear(self):
        """Wipes the memory and resets the system prompt"""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def get_messages(self) -> list[dict[str, Any]]:
        """Returns the current conversation history"""
        return self.messages
    
    def add_user_message(self, content: str):
        """Adds the user prompt to the history."""
        self.messages.append({"role": "user", "content": content})
        self._enforce_context_limit()

    def add_assistant_message(self, message_obj: Any):
        """
        Adds the exact response object from OpenAI to the history.
        It might contains tool calls as well.
        """
        self.messages.append(message_obj)
        self._enforce_context_limit()
    
    def add_tool_observartion(self, tool_call_id: str, tool_name: str, content: str):
        """
        Adds the output of a tool execution. OpenAI requires tool_call_id.
        """
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content
        })

        self._enforce_context_limit()
    
    def _enforce_context_limit(self):
        """
        Prevents the context window frmo exceeding the token limit.
        If the history gets too long, we drop the oldest messages excluding the system prompt.
        """
        if len(self.messages) > self.max_history_messages:
            safe_index = 1
            for i in range(2, len(self.messages)):
                msg = self.messages[i]

                if isinstance(msg, dict):
                    role = msg.get("role")
                else:
                    role = getattr(msg, "role", None)

                if role == "user":
                    safe_index = i
                    break

            self.messages = [self.messages[0]] + self.messages[safe_index:]
            print(f"Memory trimmed. Dropped {safe_index - 1} old messages to save tokens.")