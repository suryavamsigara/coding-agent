import os
import sys
from dotenv import load_dotenv
from google import genai

def main():
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    if len(sys.argv) < 2:
        print("Enter your question..")
        sys.exit(1)
    
    prompt = sys.argv[1]

    print(prompt)

main()
