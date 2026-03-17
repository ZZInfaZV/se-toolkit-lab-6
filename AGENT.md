# Agent Architecture

## Overview

This agent is a CLI tool that answers questions about the project documentation by using an LLM with function calling capabilities. It has tools to read files and list directories, allowing it to navigate the project wiki and find relevant information.

## Architecture

### Components

1. **CLI Interface** (`agent.py`)
   - Parses command-line arguments
   - Loads configuration from `.env.agent.secret`
   - Outputs JSON to stdout

2. **LLM Client**
   - Uses OpenAI-compatible API
   - Supports function calling for tool execution
   - Configured via environment variables

3. **Tools**
   - `read_file`: Read file contents
   - `list_files`: List directory contents

4. **Agentic Loop**
   - Manages conversation with LLM
   - Executes tool calls
   - Feeds results back to LLM

## Tools

### `read_file`

Reads the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root to the file

**Returns:**
- File contents as a string on success
- Error message if file doesn't exist or access is denied

**Example:**
```python
read_file("wiki/git-workflow.md")
# Returns: "# Git workflow\n\n..."
```

### `list_files`

Lists files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root

**Returns:**
- Newline-separated listing of entries on success
- Error message if directory doesn't exist or access is denied

**Example:**
```python
list_files("wiki")
# Returns: "api.md\narchitectural-views.md\n..."
```

### Path Security

Both tools implement path security to prevent directory traversal attacks:

1. The requested path is resolved relative to the project root
2. The path is normalized (resolves `..` and `.` components)
3. The resolved path is checked to ensure it starts with the project root
4. If the path is outside the project, access is denied

```python
def is_safe_path(requested_path: str) -> tuple[bool, str]:
    project_root = get_project_root()
    full_path = os.path.normpath(os.path.join(project_root, requested_path))
    if not full_path.startswith(project_root):
        return False, "Error: Access denied - path outside project"
    return True, full_path
```

## Agentic Loop

The agentic loop enables the LLM to iteratively gather information using tools before providing a final answer.

### Flow

```
User question
    ↓
Build messages: [system prompt, user question]
    ↓
Call LLM with tool definitions
    ↓
┌─────────────────────────────────────┐
│ LLM returns response                │
└─────────────────────────────────────┘
    │
    ├─ Has tool_calls? ──yes──▶ Execute each tool
    │                              │
    │                              ▼
    │                         Append tool call
    │                         and result to messages
    │                              │
    │                              ▼
    │                         Back to LLM (loop)
    │
    no
    │
    ▼
Extract answer and source
    ↓
Output JSON
```

### Implementation

```python
def run_agentic_loop(question: str, config: dict) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]
    
    tool_calls_log = []
    tool_call_count = 0
    
    while tool_call_count < MAX_TOOL_CALLS:
        response = call_llm(messages, config)
        
        if response.tool_calls:
            # Execute tools and feed results back
            for tool_call in response.tool_calls:
                result = execute_tool(tool_call.function.name, 
                                      json.loads(tool_call.function.arguments))
                # Log and append to messages...
                tool_call_count += 1
        else:
            # Final answer - no tool calls
            return {
                "answer": response.content,
                "source": extract_source(...),
                "tool_calls": tool_calls_log
            }
```

### Maximum Tool Calls

The loop limits to 10 tool calls maximum to prevent infinite loops. If the limit is reached, the agent returns partial results.

## System Prompt

The system prompt instructs the LLM on how to use tools effectively:

```
You are a helpful documentation assistant. You have access to tools that can 
read files and list directories in a project repository.

When answering questions:
1. Use list_files to discover what files exist in relevant directories
2. Use read_file to read the contents of specific files
3. Find the answer in the file contents
4. Include a source reference with the file path and section anchor
5. Call tools one at a time, waiting for results before making the next call
```

## Output Format

The agent outputs JSON to stdout with the following structure:

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "# Git workflow\n\n..."
    }
  ]
}
```

### Fields

- **answer** (string): The LLM's answer to the question
- **source** (string): Reference to the wiki section (file path + section anchor)
- **tool_calls** (array): All tool calls made during the agentic loop
  - **tool** (string): Name of the tool called
  - **args** (object): Arguments passed to the tool
  - **result** (string): Result returned by the tool

## Configuration

The agent loads configuration from `.env.agent.secret`:

```
LLM_API_KEY=your-api-key
LLM_API_BASE=http://your-api-server:8080/v1
LLM_MODEL=coder-model
```

## Error Handling

- **API errors**: Caught and printed to stderr, exit code 1
- **File not found**: Returns error message as tool result
- **Path traversal**: Returns "Access denied" error
- **Invalid tool**: Returns "Unknown tool" error
- **Max tool calls**: Returns partial results with warning

## Usage

```bash
# Ask a question about the documentation
uv run agent.py "How do you resolve a merge conflict?"

# Output (JSON to stdout)
{"answer": "...", "source": "wiki/git-workflow.md#...", "tool_calls": [...]}
```
