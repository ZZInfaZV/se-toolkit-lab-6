# Task 1 Plan

## LLM Provider

**Provider**: Qwen Code API (self-hosted on VM)
**Model**: `coder-model`
**API Base**: `http://10.93.25.141:8080/v1`

## Library Choice

I'll use the `openai` Python package because it's more convenient and handles
retries automatically. It supports OpenAI-compatible APIs.

## Code Structure

The agent will have three main functions:

1. `load_env()` - Load LLM_API_KEY, LLM_API_BASE, LLM_MODEL from `.env.agent.secret`
2. `call_llm(prompt)` - Make the API call using the OpenAI client
3. `main()` - Parse command-line args, call the LLM, output JSON to stdout

## Error Handling

**401 Unauthorized**: Print error to stderr, exit with code 1
**Timeout**: Print error to stderr, exit with code 1
**Parse errors**: Print error to stderr, exit with code 1
All errors go to stderr, only valid JSON goes to stdout

## Data Flow

CLI argument → main() → call_llm() → LLM API → Parse response → JSON to stdout
