# Agent Architecture

## Overview

This agent is a CLI tool that answers questions about the project by using an LLM with function calling capabilities. It has tools to read files, list directories, and query the backend API, allowing it to navigate the project wiki, read source code, and fetch live data from the running system.

## Architecture

### Components

1. **CLI Interface** (`agent.py`)
   - Parses command-line arguments
   - Loads configuration from `.env.agent.secret` and `.env.docker.secret`
   - Outputs JSON to stdout

2. **LLM Client**
   - Uses OpenAI-compatible API
   - Supports function calling for tool execution
   - Configured via environment variables

3. **Tools**
   - `read_file`: Read file contents
   - `list_files`: List directory contents
   - `query_api`: Query the backend API with authentication

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
# Returns: "git-workflow.md\napi.md\n..."
```

### `query_api` (Task 3)

Queries the backend API to get live data such as item counts, analytics, or status codes. Uses Bearer token authentication with the `LMS_API_KEY`.

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` (string, required): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:**
- JSON string with `status_code` and `body` fields
- On error, returns status code 0 with error message

**Authentication:**
The tool uses the `LMS_API_KEY` from `.env.docker.secret` and sends it as a Bearer token in the `Authorization` header.

**Example:**
```python
query_api("GET", "/items/")
# Returns: '{"status_code": 200, "body": [{"id": 1, "title": "..."}]}'

query_api("GET", "/items/", config={"lms_api_key": "my-secret-api-key"})
# Returns: '{"status_code": 200, "body": [...]}'
```

**Error Handling:**
- HTTP errors (4xx, 5xx): Returns status code and error body
- Connection errors: Returns status code 0 with connection error message
- JSON parsing errors: Returns raw response body as string

### Path Security

Both file system tools implement path security to prevent directory traversal attacks:

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
read files, list directories, and query the backend API.

When answering questions:
1. Use list_files to discover what files exist in relevant directories
2. Use read_file to read the contents of specific files (source code, 
   documentation, config files)
3. Use query_api to get live data from the running backend (item counts, 
   analytics, status codes)
4. For questions about the running system (e.g., "how many items", "what 
   status code"), use query_api
5. For questions about source code or documentation, use read_file or 
   list_files
6. Include a source reference with the file path and section anchor when 
   reading files
7. Call tools one at a time, waiting for results before making the next call
```

### Tool Selection Strategy

The LLM decides which tool to use based on the question type:

| Question Type | Example | Tool to Use |
|--------------|---------|-------------|
| Wiki/documentation | "How do I resolve a merge conflict?" | `read_file` |
| Directory listing | "What files are in the wiki?" | `list_files` |
| Live data | "How many items are in the database?" | `query_api` |
| Status codes | "What status code without auth?" | `query_api` |
| Source code | "What framework does the backend use?" | `read_file` |
| Bug diagnosis | "Why does /analytics crash?" | `query_api` + `read_file` |

## Output Format

The agent outputs JSON to stdout with the following structure:

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": [...]}"
    }
  ]
}
```

### Fields

- **answer** (string): The LLM's answer to the question
- **source** (string): Reference to the wiki section (file path + section anchor) - only for file-based questions
- **tool_calls** (array): All tool calls made during the agentic loop
  - **tool** (string): Name of the tool called
  - **args** (object): Arguments passed to the tool
  - **result** (string): Result returned by the tool

## Configuration

The agent loads configuration from multiple sources:

### `.env.agent.secret` (LLM configuration)

```
LLM_API_KEY=your-api-key
LLM_API_BASE=http://your-api-server:8080/v1
LLM_MODEL=coder-model
```

### `.env.docker.secret` (Backend configuration)

```
LMS_API_KEY=my-secret-api-key
```

### Environment Variables

The agent also reads from environment variables (for autochecker injection):
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`: LLM provider credentials
- `LMS_API_KEY`: Backend API authentication
- `AGENT_API_BASE_URL`: Backend URL (defaults to `http://localhost:42002`)

## Error Handling

- **LLM API errors**: Caught and printed to stderr, exit code 1
- **File not found**: Returns error message as tool result
- **Path traversal**: Returns "Access denied" error
- **Invalid tool**: Returns "Unknown tool" error
- **Max tool calls**: Returns partial results with warning
- **HTTP errors**: Returns status code and error body
- **Connection errors**: Returns status code 0 with error message

## Usage

```bash
# Ask a question about the documentation
uv run agent.py "How do you resolve a merge conflict?"

# Ask about live data
uv run agent.py "How many items are in the database?"

# Output (JSON to stdout)
{"answer": "...", "source": "wiki/git-workflow.md#...", "tool_calls": [...]}
```

## Lessons Learned (Task 3)

### Authentication
The backend API uses Bearer token authentication (`Authorization: Bearer <key>`), not `X-API-Key` header. This was discovered by reading the `backend/app/auth.py` source code.

### Environment Variable Loading
The agent must load from both `.env.agent.secret` (LLM config) and `.env.docker.secret` (backend config), and also check environment variables for autochecker injection.

### Tool Description Matters
The `query_api` tool description explicitly tells the LLM when to use it: "for questions about the running system". This helps the LLM distinguish between static knowledge (read from files) and dynamic data (query from API).

### Error Handling
The `query_api` tool must handle HTTP errors gracefully and return them as structured JSON so the LLM can reason about status codes and error messages.

## Benchmark Performance

The agent is tested against 10 local questions covering:
- Wiki lookups (questions 0-1)
- Source code reading (questions 2-3)
- Live data queries (questions 4-5)
- Bug diagnosis (questions 6-7)
- Open-ended reasoning (questions 8-9)

Questions 8-9 use LLM-based judging on the autochecker bot for more accurate scoring of open-ended answers.
