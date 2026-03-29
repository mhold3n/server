"""Workflow engine for LangChain/LangGraph integration with WrkHrs orchestrator."""

import asyncio
from typing import Any

import structlog
from langchain.tools import Tool
from langgraph.graph import StateGraph

logger = structlog.get_logger()


class WorkflowEngine:
    """Workflow engine for orchestrating LangChain chains and LangGraph workflows."""

    def __init__(self, orchestrator_client: Any | None = None) -> None:
        """Initialize workflow engine.

        Args:
            orchestrator_client: WrkHrsOrchestratorClient instance
        """
        self.orchestrator_client = orchestrator_client
        self.workflows: dict[str, Any] = {}
        self.chains: dict[str, Any] = {}
        self.tools: dict[str, Any] = {}

    def register_workflow(
        self,
        name: str,
        workflow: StateGraph,
    ) -> None:
        """Register a LangGraph workflow.

        Args:
            name: Workflow name
            workflow: LangGraph StateGraph instance
        """
        self.workflows[name] = workflow
        logger.info("Registered workflow", workflow_name=name)

    def register_chain(
        self,
        name: str,
        chain: Any,
    ) -> None:
        """Register a LangChain chain.

        Args:
            name: Chain name
            chain: LangChain chain instance
        """
        self.chains[name] = chain
        logger.info("Registered chain", chain_name=name)

    def register_tool(
        self,
        name: str,
        tool: Tool,
    ) -> None:
        """Register a LangChain tool.

        Args:
            name: Tool name
            tool: LangChain Tool instance
        """
        self.tools[name] = tool
        logger.info("Registered tool", tool_name=name)

    async def execute_workflow(
        self,
        workflow_name: str,
        input_data: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a registered workflow.

        Args:
            workflow_name: Name of the workflow to execute
            input_data: Input data for the workflow
            config: Optional execution configuration

        Returns:
            Workflow execution result
        """
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        workflow = self.workflows[workflow_name]

        try:
            logger.info(
                "Executing workflow",
                workflow=workflow_name,
                input_keys=list(input_data.keys()),
            )

            # Execute the workflow
            result = await workflow.ainvoke(input_data, config=config)

            logger.info(
                "Workflow execution completed",
                workflow=workflow_name,
                result_keys=list(result.keys()) if isinstance(result, dict) else None,
            )

            return {
                "status": "completed",
                "workflow": workflow_name,
                "result": result,
            }

        except Exception as e:
            logger.error(
                "Workflow execution failed",
                workflow=workflow_name,
                error=str(e),
            )
            return {
                "status": "failed",
                "workflow": workflow_name,
                "error": str(e),
            }

    async def execute_chain(
        self,
        chain_name: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a registered LangChain chain.

        Args:
            chain_name: Name of the chain to execute
            input_data: Input data for the chain

        Returns:
            Chain execution result
        """
        if chain_name not in self.chains:
            raise ValueError(f"Chain '{chain_name}' not found")

        chain = self.chains[chain_name]

        try:
            logger.info(
                "Executing chain",
                chain=chain_name,
                input_keys=list(input_data.keys()),
            )

            # Execute the chain
            result = await chain.ainvoke(input_data)

            logger.info(
                "Chain execution completed",
                chain=chain_name,
            )

            return {
                "status": "completed",
                "chain": chain_name,
                "result": result,
            }

        except Exception as e:
            logger.error(
                "Chain execution failed",
                chain=chain_name,
                error=str(e),
            )
            return {
                "status": "failed",
                "chain": chain_name,
                "error": str(e),
            }

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: str | dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a registered LangChain tool.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input for the tool

        Returns:
            Tool execution result
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        tool = self.tools[tool_name]

        try:
            logger.info(
                "Executing tool",
                tool=tool_name,
                input_type=type(tool_input).__name__,
            )

            # Execute the tool
            if asyncio.iscoroutinefunction(tool.func):
                result = await tool.func(tool_input)
            else:
                result = tool.func(tool_input)

            logger.info(
                "Tool execution completed",
                tool=tool_name,
            )

            return {
                "status": "completed",
                "tool": tool_name,
                "result": result,
            }

        except Exception as e:
            logger.error(
                "Tool execution failed",
                tool=tool_name,
                error=str(e),
            )
            return {
                "status": "failed",
                "tool": tool_name,
                "error": str(e),
            }

    def get_available_workflows(self) -> list[str]:
        """Get list of available workflow names.

        Returns:
            List of workflow names
        """
        return list(self.workflows.keys())

    def get_available_chains(self) -> list[str]:
        """Get list of available chain names.

        Returns:
            List of chain names
        """
        return list(self.chains.keys())

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

    def get_workflow_info(self, workflow_name: str) -> dict[str, Any]:
        """Get information about a workflow.

        Args:
            workflow_name: Name of the workflow

        Returns:
            Workflow information
        """
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        workflow = self.workflows[workflow_name]

        return {
            "name": workflow_name,
            "nodes": list(workflow.nodes.keys()) if hasattr(workflow, "nodes") else [],
            "edges": list(workflow.edges.keys()) if hasattr(workflow, "edges") else [],
        }

    def get_chain_info(self, chain_name: str) -> dict[str, Any]:
        """Get information about a chain.

        Args:
            chain_name: Name of the chain

        Returns:
            Chain information
        """
        if chain_name not in self.chains:
            raise ValueError(f"Chain '{chain_name}' not found")

        chain = self.chains[chain_name]

        return {
            "name": chain_name,
            "type": type(chain).__name__,
            "input_keys": getattr(chain, "input_keys", []),
            "output_keys": getattr(chain, "output_keys", []),
        }

    def get_tool_info(self, tool_name: str) -> dict[str, Any]:
        """Get information about a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        tool = self.tools[tool_name]

        return {
            "name": tool_name,
            "description": tool.description,
            "args_schema": getattr(tool, "args_schema", None),
        }
