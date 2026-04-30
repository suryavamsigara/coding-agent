import sys
from tenet.client import client
from tenet.core.agent_orchestrator import CodingAgent

def main():
    print("🤖 Tenet Coding Agent Initialized. Type 'exit' to quit.\n")

    agent = CodingAgent(client=client)

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit']:
                print("Bye")
                break

            agent.run_agent_loop(user_prompt=user_input, max_iterations=30)
        
        except KeyboardInterrupt:
            print("\nShutting down...")
            sys.exit(0)

if __name__ == "__main__":
    main()