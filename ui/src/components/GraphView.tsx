import { useCallback, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Node as FlowNode,
  Edge,
  Controls,
  Background,
  useReactFlow,
  ReactFlowProvider,
  Panel,
  Handle,
  Position,
} from "@xyflow/react";
import dagre from "dagre";
import { Node, NodeType } from "../lib/types";
import "@xyflow/react/dist/style.css";

interface GraphViewProps {
  nodes: Node[];
  selectedNode: Node | null;
  onNodeClick: (node: Node) => void;
}

const nodeTypeColors: Record<NodeType, { bg: string; border: string; text: string }> = {
  trigger: { bg: "bg-green-100", border: "border-green-500", text: "text-green-700" },
  act: { bg: "bg-blue-100", border: "border-blue-500", text: "text-blue-700" },
  assert: { bg: "bg-amber-100", border: "border-amber-500", text: "text-amber-700" },
  hook: { bg: "bg-purple-100", border: "border-purple-500", text: "text-purple-700" },
  generic: { bg: "bg-gray-100", border: "border-gray-500", text: "text-gray-700" },
};

interface CustomNodeData {
  node: Node;
  isSelected: boolean;
  isHighlighted: boolean;
}

function CustomNode({ data }: { data: CustomNodeData }) {
  const colors = nodeTypeColors[data.node.type as NodeType] || nodeTypeColors.generic;
  const isSelected = data.isSelected;
  const isHighlighted = data.isHighlighted;

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <div
        className={`px-4 py-3 rounded-lg border-2 min-w-[180px] cursor-pointer transition-all ${
          isSelected
            ? "bg-purple-100 border-purple-600 shadow-lg"
            : isHighlighted
              ? "bg-purple-50 border-purple-400 shadow-md"
              : `${colors.bg} ${colors.border}`
        }`}
      >
        <div className="flex flex-col gap-1">
          <div className={`text-xs font-semibold uppercase ${colors.text}`}>{data.node.type}</div>
          <div className="font-medium text-sm">{data.node.id}</div>
          {data.node.flow && <div className="text-xs text-gray-500">{data.node.flow}</div>}
          {data.node.source === "code" && (
            <div className="text-xs border border-gray-300 rounded px-1 py-0.5 w-fit">code</div>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-gray-400" />
    </>
  );
}

const nodeTypes = {
  custom: CustomNode,
};

function GraphContent({ nodes, selectedNode, onNodeClick }: GraphViewProps) {
  const { fitView } = useReactFlow();

  const { flowNodes, flowEdges } = useMemo(() => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({
      rankdir: "LR",
      nodesep: 150,
      ranksep: 250,
      edgesep: 50,
      marginx: 50,
      marginy: 50,
    });

    const nodeWidth = 220;
    const nodeHeight = 120;

    nodes.forEach((node) => {
      dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    nodes.forEach((node) => {
      node.dep_ids.forEach((depId) => {
        if (nodes.find((n) => n.id === depId)) {
          dagreGraph.setEdge(depId, node.id);
        }
      });
    });

    dagre.layout(dagreGraph);

    // Calculate connected nodes (entire flow) when a node is selected
    const connectedNodeIds = new Set<string>();
    if (selectedNode) {
      // Helper function to get all upstream dependencies (recursively)
      const getUpstreamNodes = (nodeId: string, visited = new Set<string>()) => {
        if (visited.has(nodeId)) return;
        visited.add(nodeId);
        connectedNodeIds.add(nodeId);

        const node = nodes.find((n) => n.id === nodeId);
        if (node) {
          node.dep_ids.forEach((depId) => {
            getUpstreamNodes(depId, visited);
          });
        }
      };

      // Helper function to get all downstream dependents (recursively)
      const getDownstreamNodes = (nodeId: string, visited = new Set<string>()) => {
        if (visited.has(nodeId)) return;
        visited.add(nodeId);
        connectedNodeIds.add(nodeId);

        nodes.forEach((node) => {
          if (node.dep_ids.includes(nodeId)) {
            getDownstreamNodes(node.id, visited);
          }
        });
      };

      // Get all connected nodes (both upstream and downstream)
      getUpstreamNodes(selectedNode.id);
      getDownstreamNodes(selectedNode.id);
    }

    const flowNodes: FlowNode[] = nodes.map((node) => {
      const nodeWithPosition = dagreGraph.node(node.id);
      const isInFlow = connectedNodeIds.has(node.id);
      const isSelected = selectedNode?.id === node.id;

      return {
        id: node.id,
        type: "custom",
        position: {
          x: nodeWithPosition.x - nodeWidth / 2,
          y: nodeWithPosition.y - nodeHeight / 2,
        },
        data: {
          node,
          isSelected,
          isHighlighted: isInFlow && !isSelected,
        },
      };
    });

    const flowEdges: Edge[] = [];
    nodes.forEach((node) => {
      node.dep_ids.forEach((depId) => {
        if (nodes.find((n) => n.id === depId)) {
          const isEdgeInFlow = connectedNodeIds.has(node.id) && connectedNodeIds.has(depId);

          flowEdges.push({
            id: `${depId}-${node.id}`,
            source: depId,
            target: node.id,
            type: "smoothstep",
            animated: isEdgeInFlow,
            style: {
              stroke: isEdgeInFlow ? "#7c3aed" : "#94a3b8",
              strokeWidth: isEdgeInFlow ? 2.5 : 2,
            },
          });
        }
      });
    });

    return { flowNodes, flowEdges };
  }, [nodes, selectedNode]);

  const onNodeClickHandler = useCallback(
    (_: React.MouseEvent, flowNode: FlowNode) => {
      const node = nodes.find((n) => n.id === flowNode.id);
      if (node) {
        onNodeClick(node);
      }
    },
    [nodes, onNodeClick]
  );

  const onPaneClick = useCallback(() => {
    onNodeClick(null as unknown as Node);
  }, [onNodeClick]);

  // Auto-center view when selection changes
  useEffect(() => {
    if (selectedNode) {
      // Get all highlighted node IDs (nodes in the flow)
      const highlightedNodeIds = flowNodes
        .filter((n) => n.data.isSelected || n.data.isHighlighted)
        .map((n) => n.id);

      if (highlightedNodeIds.length > 0) {
        // Delay to ensure layout is complete
        setTimeout(() => {
          fitView({
            nodes: highlightedNodeIds.map((id) => ({ id })),
            padding: 0.2,
            duration: 400,
          });
        }, 50);
      }
    } else {
      // No selection - fit all nodes
      setTimeout(() => {
        fitView({
          padding: 0.15,
          duration: 400,
        });
      }, 50);
    }
  }, [selectedNode, flowNodes, fitView]);

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodeClick={onNodeClickHandler}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
      >
        <Background />
        <Controls />
        <Panel position="top-left" className="bg-white p-2 rounded shadow text-sm">
          <div className="font-semibold mb-1">Legend:</div>
          <div className="flex flex-col gap-1 text-xs">
            {Object.entries(nodeTypeColors).map(([type, colors]) => (
              <div key={type} className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded ${colors.bg} border ${colors.border}`} />
                <span className="capitalize">{type}</span>
              </div>
            ))}
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}

export function GraphView(props: GraphViewProps) {
  return (
    <ReactFlowProvider>
      <GraphContent {...props} />
    </ReactFlowProvider>
  );
}
