import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { ApiSetup } from "./components/ApiSetup";
import { GraphView } from "./components/GraphView";
import { NodeDetails } from "./components/NodeDetails";
import { useNodes } from "./lib/queries";
import { apiClient } from "./lib/api";
import { Node, BaseEvalItemOutput } from "./lib/types";
import { Button } from "./components/ui/button";
import { Loader2Icon, LogOutIcon } from "lucide-react";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function MainApp() {
  const [isConfigured, setIsConfigured] = useState(() => {
    return !!apiClient.getConfig();
  });
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedEvalInfo, setSelectedEvalInfo] = useState<BaseEvalItemOutput[] | undefined>(
    undefined
  );

  const { data: nodes, isLoading, error } = useNodes();

  const handleLogout = () => {
    apiClient.clearConfig();
    setIsConfigured(false);
    setSelectedNode(null);
  };

  if (!isConfigured) {
    return <ApiSetup onConfigured={() => setIsConfigured(true)} />;
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center gap-2">
          <Loader2Icon className="h-6 w-6 animate-spin text-blue-600" />
          <p className="text-gray-600">Loading nodes...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">Error loading nodes: {error.message}</p>
          <Button onClick={handleLogout}>Reconfigure API</Button>
        </div>
      </div>
    );
  }

  if (!nodes || nodes.length === 0) {
    return (
      <div className="min-h-screen flex flex-col">
        <div className="p-4 border-b bg-white flex items-center justify-between">
          <h1 className="text-xl font-semibold">Business Use Flow Visualization</h1>
          <Button variant="outline" onClick={handleLogout}>
            <LogOutIcon className="h-4 w-4 mr-2" />
            Disconnect
          </Button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-500">No nodes found in the system</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="p-4 border-b bg-white flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-semibold">Business Use Flow Visualization</h1>
          <p className="text-sm text-gray-500">{nodes.length} nodes loaded</p>
        </div>
        <Button variant="outline" onClick={handleLogout}>
          <LogOutIcon className="h-4 w-4 mr-2" />
          Disconnect
        </Button>
      </div>

      <div className="flex-1 flex overflow-hidden min-h-0">
        <PanelGroup direction="horizontal">
          <Panel defaultSize={60} minSize={30}>
            <GraphView
              nodes={nodes}
              selectedNode={selectedNode}
              onNodeClick={setSelectedNode}
              evalInfo={selectedEvalInfo}
            />
          </Panel>
          <PanelResizeHandle className="w-1 bg-gray-200 hover:bg-blue-400 transition-colors" />
          <Panel defaultSize={40} minSize={20} maxSize={60}>
            <div className="h-full bg-white overflow-hidden">
              <NodeDetails
                node={selectedNode}
                onEvalInfoChange={setSelectedEvalInfo}
                onNodeSelect={setSelectedNode}
                allNodes={nodes}
              />
            </div>
          </Panel>
        </PanelGroup>
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MainApp />
    </QueryClientProvider>
  );
}

export default App;
