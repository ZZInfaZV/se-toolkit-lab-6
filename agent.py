import os
import sys
import json
import argparse
from openai import OpenAI

# Maximum number of tool calls allowed per question
MAX_TOOL_CALLS = 10


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


def get_project_root():
    """Get the absolute path to the project root directory."""
    return os.getcwd()


def is_safe_path(requested_path: str) -> tuple[bool, str]:
    """
    Check if a requested path is within the project directory.
    
    Returns:
        Tuple of (is_safe, resolved_path_or_error_message)
    """
    project_root = get_project_root()
    # Normalize and resolve the path
    full_path = os.path.normpath(os.path.join(project_root, requested_path))
    
    # Check if the resolved path is within project root
    if not full_path.startswith(project_root):
        return False, "Error: Access denied - path outside project"
    
    return True, full_path


def read_file(path: str) -> str:
    """
    Read the contents of a file from the project repository.
    
    Args:
        path: Relative path from project root to the file
        
    Returns:
        File contents as a string, or error message if file doesn't exist
    """
    is_safe, result = is_safe_path(path)
    if not is_safe:
        return result
    
    full_path = result
    
    try:
        if not os.path.exists(full_path):
            return f"Error: File not found: {path}"
        if not os.path.isfile(full_path):
            return f"Error: Not a file: {path}"
        
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        
    Returns:
        Newline-separated listing of entries, or error message
    """
    is_safe, result = is_safe_path(path)
    if not is_safe:
        return result
    
    full_path = result
    
    try:
        if not os.path.exists(full_path):
            return f"Error: Directory not found: {path}"
        if not os.path.isdir(full_path):
            return f"Error: Not a directory: {path}"
        
        entries = os.listdir(full_path)
        return "\n".join(sorted(entries))
    except Exception as e:
        return f"Error listing directory: {e}"


# Tool definitions for the LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root to the file"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

# Map tool names to actual functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files
}


def execute_tool(name: str, arguments: dict) -> str:
    """
    Execute a tool with the given arguments.
    
    Args:
        name: Name of the tool to execute
        arguments: Dictionary of arguments for the tool
        
    Returns:
        Result of the tool execution as a string
    """
    if name not in TOOL_FUNCTIONS:
        return f"Error: Unknown tool '{name}'"
    
    try:
        func = TOOL_FUNCTIONS[name]
        return func(**arguments)
    except Exception as e:
        return f"Error executing tool: {e}"


def extract_source_from_answer(answer: str, messages: list) -> str:
    """
    Extract a source reference from the LLM's answer.
    
    Looks for file paths mentioned in the answer and tries to find
    section anchors if present.
    
    Args:
        answer: The LLM's answer text
        messages: The conversation history
        
    Returns:
        Source reference string (e.g., "wiki/git-workflow.md#section")
    """
    # Look for wiki file paths in the answer or messages
    import re
    
    # Pattern to match wiki file paths
    wiki_pattern = r'wiki/[\w-]+\.md'
    
    # First check the answer itself
    match = re.search(wiki_pattern, answer)
    if match:
        file_path = match.group()
        # Try to find a section anchor (heading reference)
        # Look for patterns like "#section" or "section:" near the file path
        anchor_pattern = r'(' + re.escape(file_path) + r')[#]?([\w-]+)?'
        anchor_match = re.search(anchor_pattern, answer)
        if anchor_match and anchor_match.group(2):
            return f"{file_path}#{anchor_match.group(2)}"
        return file_path
    
    # Check the tool call results for file paths
    for msg in messages:
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            match = re.search(wiki_pattern, content)
            if match:
                return match.group()
    
    return ""


def call_llm(messages: list, config: dict) -> dict:
    """
    Call the LLM API with the given messages and tool definitions.
    
    Args:
        messages: List of message dictionaries
        config: Configuration dictionary with API details
        
    Returns:
        The LLM response message as a dictionary
    """
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"],
    )

    response = client.chat.completions.create(
        model=config["model"],
        messages=messages,
        tools=TOOLS,
    )

    return response.choices[0].message


def run_agentic_loop(question: str, config: dict) -> dict:
    """
    Run the agentic loop to answer a question using tools.
    
    The loop:
    1. Send question + tool definitions to LLM
    2. If LLM returns tool_calls, execute them and feed results back
    3. Repeat until LLM gives final answer or max tool calls reached
    
    Args:
        question: The user's question
        config: Configuration dictionary
        
    Returns:
        Dictionary with answer, source, and tool_calls
    """
    # System prompt instructs the LLM how to use tools
    system_prompt = """You are a helpful documentation assistant. You have access to tools that can read files and list directories in a project repository.

When answering questions:
1. Use list_files to discover what files exist in relevant directories
2. Use read_file to read the contents of specific files
3. Find the answer in the file contents
4. Include a source reference with the file path and section anchor (e.g., wiki/git-workflow.md#resolving-merge-conflicts)
5. Call tools one at a time, waiting for results before making the next call

Always provide your final answer with the source field containing the wiki file path and section."""

    # Initialize messages with system prompt and user question
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    tool_calls_log = []
    tool_call_count = 0
    
    while tool_call_count < MAX_TOOL_CALLS:
        # Call the LLM
        response_message = call_llm(messages, config)
        
        # Check if the LLM wants to call tools
        if response_message.tool_calls:
            # Execute each tool call
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Execute the tool
                result = execute_tool(tool_name, tool_args)
                
                # Log the tool call
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
                
                # Add the tool call and result to messages
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
                
                tool_call_count += 1
        else:
            # LLM returned a final answer (no tool calls)
            answer = response_message.content
            source = extract_source_from_answer(answer, messages)
            
            return {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_log
            }
    
    # Max tool calls reached - return whatever we have
    # Try to get an answer from the last response
    answer = response_message.content if response_message.content else "Maximum tool calls reached. Partial results available."
    source = extract_source_from_answer(answer, messages)
    
    return {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls_log
    }


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

        # Run the agentic loop
        result = run_agentic_loop(question, config)

        # Output JSON to stdout
        print(json.dumps(result))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
