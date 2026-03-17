# Task 2 Plan

## Overview

This task adds two tools (`read_file`, `list_files`) to the agent and implements an agentic loop that allows the LLM to call tools, get results, and reason about next steps.

## Tool Schemas

I will define two tools as function-calling schemas for the OpenAI API:

### `read_file`
- **Description**: Read the contents of a file from the project repository
- **Parameters**: 
  - `path` (string, required): Relative path from project root to the file
- **Returns**: File contents as a string, or error message if file doesn't exist

### `list_files`
- **Description**: List files and directories at a given path
- **Parameters**:
  - `path` (string, required): Relative directory path from project root
- **Returns**: Newline-separated listing of entries

## Agentic Loop Implementation

The loop will follow this flow:

1. **Send question + tool definitions** to the LLM
2. **Check response**:
   - If `tool_calls` present → execute each tool, append results as messages, repeat
   - If no tool calls → extract answer and source, output JSON
3. **Limit**: Maximum 10 tool calls per question to prevent infinite loops

### Error Handling
- **LLM API errors**: Catch exceptions, print to stderr, exit with code 1
- **File not found**: Return error message as tool result (don't crash)
- **Path traversal**: Validate paths before accessing (see Security below)
- **Invalid LLM response**: Handle gracefully with error message

## Path Security

To prevent directory traversal attacks (e.g., `../../../etc/passwd`):

1. Resolve the requested path relative to project root
2. Normalize the path (resolve `..` and `.` components)
3. Check the resolved path starts with the project root
4. If outside project, return "Error: Access denied"

```python
import os
project_root = os.getcwd()
full_path = os.path.normpath(os.path.join(project_root, requested_path))
if not full_path.startswith(project_root):
    return "Error: Access denied - path outside project"
```

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files when needed
2. Use `read_file` to find specific information
3. Include source references (file path + section anchor) in answers
4. Call tools step by step, not all at once

## Data Flow

```
User question
    ↓
Build messages array with system prompt + user question + tool definitions
    ↓
Call LLM with function_calling support
    ↓
LLM returns message with tool_calls OR final answer
    ↓
If tool_calls: execute tools → append results → back to LLM
If final answer: extract answer + source → output JSON
```

## Output Structure

```json
{
  "answer": "The final answer text",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Testing Strategy

Two regression tests:
1. **Test read_file usage**: Ask "How do you resolve a merge conflict?" → verify `read_file` in tool_calls and `wiki/git-workflow.md` in source
2. **Test list_files usage**: Ask "What files are in the wiki?" → verify `list_files` in tool_calls
