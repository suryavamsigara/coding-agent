import os
import sys
import questionary
from fastapi import FastAPI
from .agent.agent_orchestrator import CodingAgent

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "My coding agent API."}

def run_agent():
    try:
       agent = CodingAgent()
    except Exception as e:
        print(f"[Initialization Error] {e}")
        sys.exit(1)

    while True:
        try:
            prompt = questionary.text("User: ").ask()

            if prompt is None or prompt.lower() in ['exit', 'quit']:
                print("\nExiting...")
                break

            if not prompt.strip():
                continue
            agent.run(prompt)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print("\nError: ", e)
            pass

if __name__ == "__main__":
    run_agent()
