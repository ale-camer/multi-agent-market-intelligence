"""Base orchestrator abstract class establishing lifecycle and execution contracts."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, cast

from langgraph._internal._typing import StateLike
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

StateT = TypeVar("StateT", bound=StateLike)


class BaseOrchestrator(ABC, Generic[StateT]):
    """Abstract base class establishing the lifecycle contract for graph-based orchestrators.

    Subclasses must define `build_graph()` to configure nodes and edges according
    to their domain DAG requirements.
    """

    def __init__(self) -> None:
        self._graph_builder: StateGraph[StateT, Any, Any, Any] | None = None
        self._compiled_graph: CompiledStateGraph[StateT, Any, Any, Any] | None = None

    @property
    def is_compiled(self) -> bool:
        """Indicate whether the workflow graph is compiled and ready for execution."""
        return self._compiled_graph is not None

    @property
    def compiled_graph(self) -> CompiledStateGraph[StateT, Any, Any, Any]:
        """Return the compiled graph instance.

        Raises:
            RuntimeError: If the graph has not been compiled yet.
        """
        if self._compiled_graph is None:
            raise RuntimeError(
                "Orchestrator graph has not been compiled yet. Call compile() first."
            )
        return self._compiled_graph

    @abstractmethod
    def build_graph(self) -> StateGraph[StateT, Any, Any, Any]:
        """Construct and configure the nodes and edges of the DAG."""
        raise NotImplementedError

    def compile(self) -> CompiledStateGraph[StateT, Any, Any, Any]:
        """Build and compile the workflow graph.

        Returns:
            The compiled executable graph.
        """
        builder = self.build_graph()
        self._graph_builder = builder
        self._compiled_graph = builder.compile()
        return self._compiled_graph

    def run(self, initial_state: StateT) -> StateT:
        """Execute the workflow synchronously from the provided initial state.

        If the graph has not been compiled yet, it is compiled automatically.

        Args:
            initial_state: The starting state dictionary or model.

        Returns:
            The final state after traversing the DAG to completion.
        """
        self._validate_state(initial_state)
        if self._compiled_graph is None:
            self.compile()
        raw_result = self.compiled_graph.invoke(initial_state)
        return cast(StateT, raw_result)

    def invoke(self, initial_state: StateT) -> StateT:
        """Alias for run() aligned with LangGraph invocation conventions."""
        return self.run(initial_state)

    async def arun(self, initial_state: StateT) -> StateT:
        """Execute the workflow asynchronously from the provided initial state.

        If the graph has not been compiled yet, it is compiled automatically.

        Args:
            initial_state: The starting state dictionary or model.

        Returns:
            The final state after traversing the DAG to completion.
        """
        self._validate_state(initial_state)
        if self._compiled_graph is None:
            self.compile()
        raw_result = await self.compiled_graph.ainvoke(initial_state)
        return cast(StateT, raw_result)

    async def ainvoke(self, initial_state: StateT) -> StateT:
        """Alias for arun() aligned with LangGraph async invocation conventions."""
        return await self.arun(initial_state)

    def _validate_state(self, state: StateT) -> None:
        """Validate the format of the provided initial state.

        Args:
            state: State to validate.

        Raises:
            TypeError: If the state does not match expected mapping structures.
        """
        if not isinstance(state, dict):
            raise TypeError(
                f"initial_state must be a dictionary or mapping, got {type(state).__name__}"
            )
