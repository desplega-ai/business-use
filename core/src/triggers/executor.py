"""Trigger execution for flow ensure command.

Executes trigger nodes (HTTP requests, bash commands) and extracts run_ids.
"""

import asyncio
import logging
import subprocess
from typing import Any, TypedDict

import httpx

from src.execution.python_eval import PythonEvaluator
from src.models import Expr, Node
from src.secrets_manager.secrets import substitute_handler_input

log = logging.getLogger(__name__)


class TriggerContext(TypedDict):
    """Context passed to run_id extractor expression.

    Attributes:
        input: Request/command input parameters
        output: Response/command output data
    """

    input: dict[str, Any]
    output: dict[str, Any]


async def execute_http_trigger(node: Node) -> TriggerContext:
    """Execute HTTP request trigger.

    Args:
        node: Trigger node with handler='http_request'

    Returns:
        TriggerContext with input (request params) and output (response data)

    Raises:
        ValueError: If required params missing
        httpx.HTTPError: If HTTP request fails
    """
    if not node.handler_input or not node.handler_input.params:
        raise ValueError(f"Trigger node '{node.id}' missing handler_input.params")

    # Substitute secrets in params
    params_dict = substitute_handler_input(node.handler_input)
    params = params_dict["params"]

    url = params.get("url")
    method = params.get("method", "GET")
    headers = params.get("headers", {})
    body = params.get("body")
    timeout_ms = params.get("timeout_ms", 30000)

    if not url:
        raise ValueError(f"Trigger node '{node.id}' missing handler_input.params.url")

    log.info(f"Executing HTTP trigger: {method} {url}")

    # Prepare request
    timeout = httpx.Timeout(timeout_ms / 1000.0)
    request_data: dict[str, Any] = {
        "method": method,
        "url": url,
        "headers": headers,
        "timeout": timeout,
    }

    if body is not None:
        # If body is a string, send as-is (could be JSON string)
        request_data["content"] = body

    # Execute HTTP request
    async with httpx.AsyncClient() as client:
        response = await client.request(**request_data)

    # Raise for HTTP errors (4xx, 5xx)
    response.raise_for_status()

    # Try to parse JSON response, fallback to text
    try:
        response_data = response.json()
    except Exception:
        response_data = {"text": response.text, "status_code": response.status_code}

    log.info(f"HTTP trigger completed: {response.status_code}")

    # Build context
    context: TriggerContext = {
        "input": {
            "method": method,
            "url": url,
            "headers": headers,
            "body": body,
        },
        "output": response_data,
    }

    return context


async def execute_command_trigger(node: Node) -> TriggerContext:
    """Execute bash command trigger.

    Args:
        node: Trigger node with handler='command'

    Returns:
        TriggerContext with input (command) and output (stdout, stderr, returncode)

    Raises:
        ValueError: If required params missing
        subprocess.CalledProcessError: If command fails
    """
    if not node.handler_input or not node.handler_input.params:
        raise ValueError(f"Trigger node '{node.id}' missing handler_input.params")

    # Substitute secrets in params
    params_dict = substitute_handler_input(node.handler_input)
    params = params_dict["params"]

    command = params.get("command")
    timeout_ms = params.get("timeout_ms", 30000)

    if not command:
        raise ValueError(
            f"Trigger node '{node.id}' missing handler_input.params.command"
        )

    log.info(f"Executing command trigger: {command}")

    # Execute command
    timeout_s = timeout_ms / 1000.0
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout_s
        )
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise TimeoutError(f"Command timed out after {timeout_ms}ms") from None

    # Decode output
    stdout_str = stdout.decode() if stdout else ""
    stderr_str = stderr.decode() if stderr else ""

    if process.returncode != 0:
        log.error(f"Command failed with exit code {process.returncode}")
        log.error(f"stderr: {stderr_str}")
        returncode = process.returncode if process.returncode is not None else -1
        raise subprocess.CalledProcessError(returncode, command, stdout_str, stderr_str)

    log.info(f"Command trigger completed: exit code {process.returncode}")

    # Build context
    context: TriggerContext = {
        "input": {
            "command": command,
        },
        "output": {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": process.returncode,
        },
    }

    return context


async def execute_trigger(node: Node) -> TriggerContext:
    """Execute trigger node based on handler type.

    Dispatches to appropriate executor based on node.handler.

    Args:
        node: Trigger node to execute

    Returns:
        TriggerContext with input and output

    Raises:
        ValueError: If handler type unsupported or params invalid
        httpx.HTTPError: If HTTP request fails
        subprocess.CalledProcessError: If command fails
    """
    if node.handler == "http_request":
        return await execute_http_trigger(node)
    elif node.handler == "command":
        return await execute_command_trigger(node)
    else:
        raise ValueError(
            f"Unsupported handler type for trigger: {node.handler}. "
            f"Supported: http_request, command"
        )


def extract_run_id(context: TriggerContext, extractor: Expr) -> str:
    """Extract run_id from trigger context using Python expression.

    The expression has access to:
    - input: Request/command input parameters
    - output: Response/command output data

    Args:
        context: Trigger context (input + output)
        extractor: Expr with Python script to extract run_id

    Returns:
        Extracted run_id string

    Raises:
        ValueError: If expression fails or returns non-string

    Examples:
        >>> context = {"input": {...}, "output": {"data": {"payment_id": "pmt_123"}}}
        >>> extractor = Expr(engine="python", script="output['data']['payment_id']")
        >>> extract_run_id(context, extractor)
        "pmt_123"
    """
    if extractor.engine != "python":
        raise ValueError(
            f"Only Python expressions supported for run_id extraction, got: {extractor.engine}"
        )

    evaluator = PythonEvaluator()

    # Prepare context for evaluation
    # The expression has access to 'input' and 'output' variables
    eval_variables = {
        "input": context["input"],
        "output": context["output"],
    }

    try:
        # Evaluate expression using eval_expr (returns any type, not just bool)
        result = evaluator.eval_expr(extractor.script, eval_variables)

        # Ensure result is a string
        if not isinstance(result, str):
            result_str = str(result)
            log.warning(
                f"run_id extractor returned non-string ({type(result).__name__}), converting to string: {result_str}"
            )
            return result_str

        if not result:
            raise ValueError("run_id extractor returned empty string")

        return result

    except Exception as e:
        log.error(f"Failed to extract run_id from context: {e}")
        log.debug(f"Context: {context}")
        log.debug(f"Expression: {extractor.script}")
        raise ValueError(f"Failed to extract run_id: {e}") from e
