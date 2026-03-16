import os
import sys
import json
import argparse
from openai import OpenAI

def load_env():
    """Load configuration from .env.agent.secret file."""
    config = {}
    with open(".env.agent.secret", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return {
        "api_key": config.get("LLM_API_KEY"),
        "api_base": config.get("LLM_API_BASE"),
        "model": config.get("LLM_MODEL"),
    }
def call_llm(prompt: str, config: dict) -> str:
    """Call the LLM API and return the response."""
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"],
    )
    
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    return response.choices[0].message.content

def main():
    """Main entry point."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: agent.py <question>", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    try:
        # Load configuration
        config = load_env()

        # Call the LLM
        answer = call_llm(question, config)

        # Output JSON to stdout
        result = {
            "answer": answer,
            "tool_calls": []
        }
        print(json.dumps(result))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()