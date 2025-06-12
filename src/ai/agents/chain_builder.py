"""
Agent Chain Builder Module

Provides functionality for building and executing chains of agents
with conditional routing and data transformation.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json

from ai.agents.models import (
    AgentType, AgentTask, AgentResponse, ChainNode, ChainNodeType,
    AgentChain
)
from managers.agent_manager import agent_manager

logger = logging.getLogger(__name__)


class ExecutionContext:
    """Context for chain execution containing shared data."""
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.results: Dict[str, AgentResponse] = {}
        self.errors: List[str] = []
        self.executed_nodes: List[str] = []
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context data."""
        return self.data.get(key, default)
        
    def set(self, key: str, value: Any):
        """Set value in context data."""
        self.data[key] = value
        
    def add_result(self, node_id: str, response: AgentResponse):
        """Add agent execution result."""
        self.results[node_id] = response
        self.executed_nodes.append(node_id)
        
    def add_error(self, error: str):
        """Add error message."""
        self.errors.append(error)
        

class ChainExecutor:
    """Executes agent chains with support for complex workflows."""
    
    def __init__(self):
        self.transformers: Dict[str, Callable] = {}
        self.conditions: Dict[str, Callable] = {}
        self._register_default_transformers()
        self._register_default_conditions()
        
    def execute_chain(self, chain: AgentChain, initial_input: Dict[str, Any]) -> ExecutionContext:
        """Execute an agent chain.
        
        Args:
            chain: The agent chain to execute
            initial_input: Initial input data
            
        Returns:
            Execution context with results
        """
        context = ExecutionContext()
        context.data.update(initial_input)
        
        # Build node map for quick lookup
        node_map = {node.id: node for node in chain.nodes}
        
        # Find and execute starting node
        if chain.start_node_id not in node_map:
            context.add_error(f"Start node {chain.start_node_id} not found")
            return context
            
        # Execute chain
        self._execute_node(chain.start_node_id, node_map, context)
        
        return context
        
    def _execute_node(
        self, 
        node_id: str, 
        node_map: Dict[str, ChainNode],
        context: ExecutionContext
    ) -> Optional[Any]:
        """Execute a single node in the chain.
        
        Args:
            node_id: ID of the node to execute
            node_map: Map of all nodes
            context: Execution context
            
        Returns:
            Node execution result
        """
        if node_id in context.executed_nodes:
            logger.warning(f"Node {node_id} already executed, skipping to prevent loops")
            return None
            
        node = node_map.get(node_id)
        if not node:
            context.add_error(f"Node {node_id} not found")
            return None
            
        logger.info(f"Executing node {node.name} (type: {node.type})")
        
        try:
            # Execute based on node type
            if node.type == ChainNodeType.AGENT:
                result = self._execute_agent_node(node, context)
            elif node.type == ChainNodeType.CONDITION:
                result = self._execute_condition_node(node, node_map, context)
            elif node.type == ChainNodeType.TRANSFORMER:
                result = self._execute_transformer_node(node, context)
            elif node.type == ChainNodeType.AGGREGATOR:
                result = self._execute_aggregator_node(node, context)
            elif node.type == ChainNodeType.PARALLEL:
                result = self._execute_parallel_node(node, node_map, context)
            elif node.type == ChainNodeType.LOOP:
                result = self._execute_loop_node(node, node_map, context)
            else:
                context.add_error(f"Unknown node type: {node.type}")
                return None
                
            # Execute output nodes
            for output_id in node.outputs:
                self._execute_node(output_id, node_map, context)
                
            return result
            
        except Exception as e:
            context.add_error(f"Error executing node {node.name}: {str(e)}")
            logger.error(f"Error executing node {node.name}", exc_info=True)
            return None
            
    def _execute_agent_node(self, node: ChainNode, context: ExecutionContext) -> Optional[AgentResponse]:
        """Execute an agent node.
        
        Args:
            node: The agent node
            context: Execution context
            
        Returns:
            Agent response if successful
        """
        if not node.agent_type:
            context.add_error(f"Agent node {node.name} missing agent_type")
            return None
            
        # Prepare task from context
        task_description = node.config.get("task_description", "Execute agent task")
        task_context = node.config.get("context_template", "")
        
        # Format context template with context data
        if task_context:
            try:
                task_context = task_context.format(**context.data)
            except KeyError as e:
                logger.warning(f"Missing context key: {e}")
                
        # Get input data
        input_data = {}
        for input_key in node.config.get("input_keys", []):
            if input_key in context.data:
                input_data[input_key] = context.data[input_key]
                
        # Create and execute task
        task = AgentTask(
            task_description=task_description,
            context=task_context,
            input_data=input_data
        )
        
        response = agent_manager.execute_agent_task(node.agent_type, task)
        
        if response:
            context.add_result(node.id, response)
            
            # Store output in context
            output_key = node.config.get("output_key", f"{node.id}_result")
            context.set(output_key, response.result)
            
        return response
        
    def _execute_condition_node(
        self, 
        node: ChainNode, 
        node_map: Dict[str, ChainNode],
        context: ExecutionContext
    ) -> bool:
        """Execute a condition node.
        
        Args:
            node: The condition node
            node_map: Map of all nodes
            context: Execution context
            
        Returns:
            Condition result
        """
        condition_name = node.config.get("condition")
        if not condition_name:
            context.add_error(f"Condition node {node.name} missing condition")
            return False
            
        # Get condition function
        condition_func = self.conditions.get(condition_name)
        if not condition_func:
            # Try to evaluate as expression
            try:
                result = eval(condition_name, {"__builtins__": {}}, context.data)
            except Exception as e:
                context.add_error(f"Failed to evaluate condition: {e}")
                return False
        else:
            result = condition_func(context)
            
        # Execute appropriate branch
        if result:
            true_outputs = node.config.get("true_outputs", [])
            for output_id in true_outputs:
                if output_id in node_map:
                    self._execute_node(output_id, node_map, context)
        else:
            false_outputs = node.config.get("false_outputs", [])
            for output_id in false_outputs:
                if output_id in node_map:
                    self._execute_node(output_id, node_map, context)
                    
        return result
        
    def _execute_transformer_node(self, node: ChainNode, context: ExecutionContext) -> Any:
        """Execute a transformer node.
        
        Args:
            node: The transformer node
            context: Execution context
            
        Returns:
            Transformed data
        """
        transformer_name = node.config.get("transformer")
        if not transformer_name:
            context.add_error(f"Transformer node {node.name} missing transformer")
            return None
            
        transformer_func = self.transformers.get(transformer_name)
        if not transformer_func:
            context.add_error(f"Transformer {transformer_name} not found")
            return None
            
        # Get input data
        input_key = node.config.get("input_key")
        input_data = context.get(input_key) if input_key else context.data
        
        # Transform data
        result = transformer_func(input_data, node.config)
        
        # Store output
        output_key = node.config.get("output_key", f"{node.id}_result")
        context.set(output_key, result)
        
        return result
        
    def _execute_aggregator_node(self, node: ChainNode, context: ExecutionContext) -> Any:
        """Execute an aggregator node.
        
        Args:
            node: The aggregator node
            context: Execution context
            
        Returns:
            Aggregated data
        """
        # Get input keys
        input_keys = node.config.get("input_keys", [])
        if not input_keys:
            context.add_error(f"Aggregator node {node.name} missing input_keys")
            return None
            
        # Collect input data
        inputs = {}
        for key in input_keys:
            if key in context.data:
                inputs[key] = context.data[key]
                
        # Perform aggregation
        aggregation_type = node.config.get("type", "combine")
        
        if aggregation_type == "combine":
            result = "\n\n".join(str(v) for v in inputs.values())
        elif aggregation_type == "merge":
            result = {}
            for v in inputs.values():
                if isinstance(v, dict):
                    result.update(v)
        elif aggregation_type == "list":
            result = list(inputs.values())
        else:
            context.add_error(f"Unknown aggregation type: {aggregation_type}")
            return None
            
        # Store output
        output_key = node.config.get("output_key", f"{node.id}_result")
        context.set(output_key, result)
        
        return result
        
    def _execute_parallel_node(
        self, 
        node: ChainNode, 
        node_map: Dict[str, ChainNode],
        context: ExecutionContext
    ) -> List[Any]:
        """Execute a parallel node.
        
        Args:
            node: The parallel node
            node_map: Map of all nodes
            context: Execution context
            
        Returns:
            List of results from parallel execution
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        parallel_nodes = node.config.get("parallel_nodes", [])
        if not parallel_nodes:
            context.add_error(f"Parallel node {node.name} missing parallel_nodes")
            return []
            
        results = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            
            for node_id in parallel_nodes:
                if node_id in node_map:
                    # Create separate context for parallel execution
                    parallel_context = ExecutionContext()
                    parallel_context.data.update(context.data)
                    
                    future = executor.submit(
                        self._execute_node,
                        node_id,
                        node_map,
                        parallel_context
                    )
                    futures[future] = (node_id, parallel_context)
                    
            # Collect results
            for future in as_completed(futures):
                node_id, parallel_context = futures[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Merge results back to main context
                    context.results.update(parallel_context.results)
                    context.errors.extend(parallel_context.errors)
                    
                    # Optionally merge data
                    if node.config.get("merge_data", False):
                        context.data.update(parallel_context.data)
                        
                except Exception as e:
                    context.add_error(f"Error in parallel execution of {node_id}: {e}")
                    
        return results
        
    def _execute_loop_node(
        self, 
        node: ChainNode, 
        node_map: Dict[str, ChainNode],
        context: ExecutionContext
    ) -> List[Any]:
        """Execute a loop node.
        
        Args:
            node: The loop node
            node_map: Map of all nodes
            context: Execution context
            
        Returns:
            List of results from loop iterations
        """
        # Get loop configuration
        loop_type = node.config.get("loop_type", "count")
        max_iterations = node.config.get("max_iterations", 10)
        loop_nodes = node.config.get("loop_nodes", [])
        
        if not loop_nodes:
            context.add_error(f"Loop node {node.name} missing loop_nodes")
            return []
            
        results = []
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Check loop condition
            if loop_type == "count":
                count = node.config.get("count", 1)
                if iteration > count:
                    break
            elif loop_type == "condition":
                condition = node.config.get("condition")
                if condition:
                    try:
                        if not eval(condition, {"__builtins__": {}}, context.data):
                            break
                    except Exception as e:
                        context.add_error(f"Failed to evaluate loop condition: {e}")
                        break
                        
            # Execute loop body
            context.set("loop_iteration", iteration)
            
            for node_id in loop_nodes:
                if node_id in node_map:
                    result = self._execute_node(node_id, node_map, context)
                    results.append(result)
                    
        return results
        
    def register_transformer(self, name: str, func: Callable):
        """Register a custom transformer function.
        
        Args:
            name: Transformer name
            func: Transformer function
        """
        self.transformers[name] = func
        
    def register_condition(self, name: str, func: Callable):
        """Register a custom condition function.
        
        Args:
            name: Condition name
            func: Condition function
        """
        self.conditions[name] = func
        
    def _register_default_transformers(self):
        """Register default transformers."""
        
        def json_to_dict(data: str, config: dict) -> dict:
            """Convert JSON string to dictionary."""
            try:
                return json.loads(data)
            except:
                return {}
                
        def extract_field(data: dict, config: dict) -> Any:
            """Extract field from dictionary."""
            field_name = config.get("field")
            return data.get(field_name) if field_name else None
            
        def format_template(data: Any, config: dict) -> str:
            """Format template with data."""
            template = config.get("template", "{}")
            try:
                if isinstance(data, dict):
                    return template.format(**data)
                else:
                    return template.format(data)
            except:
                return str(data)
                
        self.transformers["json_to_dict"] = json_to_dict
        self.transformers["extract_field"] = extract_field
        self.transformers["format_template"] = format_template
        
    def _register_default_conditions(self):
        """Register default conditions."""
        
        def has_key(context: ExecutionContext) -> bool:
            """Check if context has a specific key."""
            key = context.get("condition_key")
            return key in context.data if key else False
            
        def is_not_empty(context: ExecutionContext) -> bool:
            """Check if a value is not empty."""
            key = context.get("condition_key")
            value = context.get(key)
            return bool(value)
            
        def contains_text(context: ExecutionContext) -> bool:
            """Check if text contains substring."""
            text_key = context.get("text_key")
            search_text = context.get("search_text")
            
            if text_key and search_text:
                text = context.get(text_key, "")
                return search_text in str(text)
            return False
            
        self.conditions["has_key"] = has_key
        self.conditions["is_not_empty"] = is_not_empty
        self.conditions["contains_text"] = contains_text


class ChainBuilder:
    """Builder for creating agent chains programmatically."""
    
    def __init__(self, name: str, description: str = ""):
        self.chain = AgentChain(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            nodes=[],
            start_node_id="",
            metadata={}
        )
        self._current_node: Optional[ChainNode] = None
        
    def add_agent_node(
        self, 
        name: str, 
        agent_type: AgentType,
        task_description: str = "",
        context_template: str = "",
        output_key: str = ""
    ) -> 'ChainBuilder':
        """Add an agent node to the chain.
        
        Args:
            name: Node name
            agent_type: Type of agent
            task_description: Task description
            context_template: Context template
            output_key: Key to store output
            
        Returns:
            Self for chaining
        """
        node = ChainNode(
            id=str(uuid.uuid4()),
            type=ChainNodeType.AGENT,
            name=name,
            agent_type=agent_type,
            config={
                "task_description": task_description,
                "context_template": context_template,
                "output_key": output_key or f"{name}_result"
            }
        )
        
        self._add_node(node)
        return self
        
    def add_condition_node(
        self,
        name: str,
        condition: str,
        true_node: Optional[str] = None,
        false_node: Optional[str] = None
    ) -> 'ChainBuilder':
        """Add a condition node to the chain.
        
        Args:
            name: Node name
            condition: Condition expression or name
            true_node: Node to execute if true
            false_node: Node to execute if false
            
        Returns:
            Self for chaining
        """
        node = ChainNode(
            id=str(uuid.uuid4()),
            type=ChainNodeType.CONDITION,
            name=name,
            config={
                "condition": condition,
                "true_outputs": [true_node] if true_node else [],
                "false_outputs": [false_node] if false_node else []
            }
        )
        
        self._add_node(node)
        return self
        
    def add_transformer_node(
        self,
        name: str,
        transformer: str,
        input_key: Optional[str] = None,
        output_key: Optional[str] = None,
        **config
    ) -> 'ChainBuilder':
        """Add a transformer node to the chain.
        
        Args:
            name: Node name
            transformer: Transformer name
            input_key: Input data key
            output_key: Output data key
            **config: Additional configuration
            
        Returns:
            Self for chaining
        """
        node_config = {
            "transformer": transformer,
            "output_key": output_key or f"{name}_result"
        }
        
        if input_key:
            node_config["input_key"] = input_key
            
        node_config.update(config)
        
        node = ChainNode(
            id=str(uuid.uuid4()),
            type=ChainNodeType.TRANSFORMER,
            name=name,
            config=node_config
        )
        
        self._add_node(node)
        return self
        
    def connect(self, from_node: str, to_node: str) -> 'ChainBuilder':
        """Connect two nodes.
        
        Args:
            from_node: Source node name
            to_node: Target node name
            
        Returns:
            Self for chaining
        """
        from_node_obj = self._find_node_by_name(from_node)
        to_node_obj = self._find_node_by_name(to_node)
        
        if from_node_obj and to_node_obj:
            if to_node_obj.id not in from_node_obj.outputs:
                from_node_obj.outputs.append(to_node_obj.id)
            if from_node_obj.id not in to_node_obj.inputs:
                to_node_obj.inputs.append(from_node_obj.id)
                
        return self
        
    def set_start_node(self, name: str) -> 'ChainBuilder':
        """Set the starting node.
        
        Args:
            name: Node name
            
        Returns:
            Self for chaining
        """
        node = self._find_node_by_name(name)
        if node:
            self.chain.start_node_id = node.id
        return self
        
    def build(self) -> AgentChain:
        """Build and return the agent chain.
        
        Returns:
            The completed agent chain
        """
        # Set start node if not set
        if not self.chain.start_node_id and self.chain.nodes:
            self.chain.start_node_id = self.chain.nodes[0].id
            
        return self.chain
        
    def _add_node(self, node: ChainNode):
        """Add a node to the chain."""
        self.chain.nodes.append(node)
        
        # Auto-connect to previous node
        if self._current_node:
            self.connect(self._current_node.name, node.name)
            
        self._current_node = node
        
    def _find_node_by_name(self, name: str) -> Optional[ChainNode]:
        """Find a node by name."""
        for node in self.chain.nodes:
            if node.name == name:
                return node
        return None


# Example usage
def create_medical_workflow_chain() -> AgentChain:
    """Create an example medical workflow chain."""
    builder = ChainBuilder("Medical Documentation Workflow")
    
    return (builder
        .add_agent_node(
            "transcript_processor",
            AgentType.DATA_EXTRACTION,
            "Extract medical information from transcript",
            output_key="extracted_data"
        )
        .add_condition_node(
            "check_urgency",
            "len(extracted_data) > 0 and 'urgent' in extracted_data",
            true_node="urgent_handler",
            false_node="normal_flow"
        )
        .add_agent_node(
            "urgent_handler",
            AgentType.WORKFLOW,
            "Handle urgent medical case",
            context_template="Urgent case detected: {extracted_data}"
        )
        .add_agent_node(
            "normal_flow",
            AgentType.SYNOPSIS,
            "Generate clinical synopsis",
            context_template="Patient data: {extracted_data}"
        )
        .add_agent_node(
            "diagnostic_analysis",
            AgentType.DIAGNOSTIC,
            "Analyze for potential diagnoses",
            context_template="Synopsis: {normal_flow_result}"
        )
        .set_start_node("transcript_processor")
        .build()
    )