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
