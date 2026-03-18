"""Regression tests for agent.py CLI.

These tests verify that the agent outputs valid JSON with the required fields.
Run with: uv run pytest tests/test_agent.py -v
"""

import json
import subprocess
import sys
import pytest


class TestAgentOutput:
    """Tests for agent.py output structure."""

    @pytest.mark.asyncio
    async def test_agent_returns_valid_json(self):
        """Test that agent.py outputs valid JSON to stdout."""
        result = subprocess.run(
            [sys.executable, "agent.py", "What is 2 + 2?"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Exit code should be 0 on success
        assert result.returncode == 0, f"Agent failed with: {result.stderr}"

        # stdout should be valid JSON
        output = json.loads(result.stdout)
        assert isinstance(output, dict), "Output should be a JSON object"

    @pytest.mark.asyncio
    async def test_agent_has_required_fields(self):
        """Test that the JSON output contains 'answer' and 'tool_calls' fields."""
        result = subprocess.run(
            [sys.executable, "agent.py", "What does REST stand for?"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"Agent failed with: {result.stderr}"

        output = json.loads(result.stdout)


        # Check required fields exist
        assert "answer" in output, "Missing 'answer' field in output"
        assert "tool_calls" in output, "Missing 'tool_calls' field in output"

        # Check field types
        assert isinstance(output["answer"], str), "'answer' should be a string"
        assert isinstance(output["tool_calls"], list), "'tool_calls' should be an array"

    @pytest.mark.asyncio
    async def test_agent_answer_is_not_empty(self):
        """Test that the agent provides a non-empty answer."""
        result = subprocess.run(
            [sys.executable, "agent.py", "What is the capital of France?"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"Agent failed with: {result.stderr}"

        output = json.loads(result.stdout)

        # Answer should not be empty
        assert output["answer"], "Answer should not be empty"
        assert len(output["answer"].strip()) > 0, "Answer should contain non-whitespace characters"

    @pytest.mark.asyncio
    async def test_agent_uses_read_file_for_wiki_question(self):
        """Test that agent uses read_file tool when asked about wiki content."""
        result = subprocess.run(
            [sys.executable, "agent.py", "How do you resolve a merge conflict?"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"Agent failed with: {result.stderr}"

        output = json.loads(result.stdout)

        # Should have used read_file tool
        tool_names = [tc["tool"] for tc in output["tool_calls"]]
        assert "read_file" in tool_names, "Agent should use read_file tool for wiki questions"

        # Source should reference wiki/git-workflow.md
        assert "wiki/git-workflow.md" in output["source"], \
            f"Source should reference wiki/git-workflow.md, got: {output['source']}"

    @pytest.mark.asyncio
    async def test_agent_uses_list_files_for_directory_question(self):
        """Test that agent uses list_files tool when asked about directory contents."""
        result = subprocess.run(
            [sys.executable, "agent.py", "What files are in the wiki?"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"Agent failed with: {result.stderr}"

        output = json.loads(result.stdout)

        # Should have used list_files tool
        tool_names = [tc["tool"] for tc in output["tool_calls"]]
        assert "list_files" in tool_names, "Agent should use list_files tool for directory questions"

        # Should have a non-empty answer
        assert output["answer"], "Answer should not be empty"

    @pytest.mark.asyncio
    async def test_agent_uses_query_api_for_item_count(self):
        """Test that agent uses query_api tool when asked about database item count."""
        result = subprocess.run(
            [sys.executable, "agent.py", "How many items are in the database?"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"Agent failed with: {result.stderr}"

        output = json.loads(result.stdout)

        # Should have used query_api tool
        tool_names = [tc["tool"] for tc in output["tool_calls"]]
        assert "query_api" in tool_names, "Agent should use query_api tool for data queries"

        # Answer should contain a number
        import re
        numbers = re.findall(r'\d+', output["answer"])
        assert len(numbers) > 0, "Answer should contain a number"

    @pytest.mark.asyncio
    async def test_agent_uses_query_api_for_status_code(self):
        """Test that agent uses query_api tool when asked about HTTP status codes."""
        result = subprocess.run(
            [sys.executable, "agent.py", "What HTTP status code does the API return when you request /items/ without authentication?"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"Agent failed with: {result.stderr}"

        output = json.loads(result.stdout)

        # Should have used query_api tool
        tool_names = [tc["tool"] for tc in output["tool_calls"]]
        assert "query_api" in tool_names, "Agent should use query_api tool for status code questions"

        # Answer should contain 401 or 403 (unauthorized/forbidden)
        assert "401" in output["answer"] or "403" in output["answer"], \
            f"Answer should contain 401 or 403, got: {output['answer']}"
