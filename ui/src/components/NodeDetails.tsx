import { useState } from "react";
import { Node } from "../lib/types";
import { useEvents, useEvalOutputs, useRunEval } from "../lib/queries";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { PlayIcon, Loader2Icon } from "lucide-react";

interface NodeDetailsProps {
  node: Node | null;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    passed: "bg-green-100 text-green-700 border-green-300",
    failed: "bg-red-100 text-red-700 border-red-300",
    running: "bg-blue-100 text-blue-700 border-blue-300",
    pending: "bg-yellow-100 text-yellow-700 border-yellow-300",
    skipped: "bg-gray-100 text-gray-700 border-gray-300",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${
        colors[status] || colors.pending
      }`}
    >
      {status}
    </span>
  );
}

export function NodeDetails({ node }: NodeDetailsProps) {
  const [selectedTab, setSelectedTab] = useState<"details" | "events" | "runs">("details");
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const { data: events, isLoading: loadingEvents } = useEvents(node?.flow, node?.id, 20, 0);

  const { data: evalOutputs, isLoading: loadingOutputs } = useEvalOutputs(
    node ? [node.flow] : undefined,
    undefined,
    20,
    0
  );

  const runEval = useRunEval();

  const handleEvaluate = (eventId: string) => {
    runEval.mutate({ ev_id: eventId, whole_graph: true });
  };

  if (!node) {
    return (
      <div className="p-6 h-full flex items-center justify-center text-gray-500">
        <p>Select a node to view details</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="border-b">
        <div className="flex">
          {(["details", "events", "runs"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setSelectedTab(tab)}
              className={`px-4 py-3 text-sm font-medium border-b-2 capitalize ${
                selectedTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {selectedTab === "details" && (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-500">Node ID</h3>
              <p className="mt-1 text-sm font-mono">{node.id}</p>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-500">Flow</h3>
              <p className="mt-1 text-sm">{node.flow}</p>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-500">Type</h3>
              <p className="mt-1 text-sm capitalize">{node.type}</p>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-500">Source</h3>
              <p className="mt-1 text-sm capitalize">{node.source}</p>
            </div>

            {node.description && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Description</h3>
                <p className="mt-1 text-sm">{node.description}</p>
              </div>
            )}

            {node.dep_ids.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Dependencies</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {node.dep_ids.map((depId) => (
                    <span key={depId} className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                      {depId}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {node.filter && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Filter</h3>
                <pre className="mt-1 text-xs bg-gray-50 p-2 rounded overflow-auto">
                  {node.filter.script}
                </pre>
              </div>
            )}

            {node.validator && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Validator</h3>
                <pre className="mt-1 text-xs bg-gray-50 p-2 rounded overflow-auto">
                  {node.validator.script}
                </pre>
              </div>
            )}
          </div>
        )}

        {selectedTab === "events" && (
          <div className="space-y-4">
            {loadingEvents && (
              <div className="flex items-center justify-center py-8">
                <Loader2Icon className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            )}

            {!loadingEvents && (!events || events.length === 0) && (
              <p className="text-center text-gray-500 py-8">No events found</p>
            )}

            {events?.map((event) => (
              <Card key={event.id}>
                <CardHeader
                  className="cursor-pointer"
                  onClick={() => setExpandedEventId(expandedEventId === event.id ? null : event.id)}
                >
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-mono">
                      {event.id.substring(0, 8)}...
                    </CardTitle>
                    <span className="text-xs text-gray-500">
                      {new Date(event.ts / 1_000_000).toLocaleString()}
                    </span>
                  </div>
                </CardHeader>
                {expandedEventId === event.id && (
                  <CardContent className="space-y-3">
                    <div>
                      <h4 className="text-xs font-medium text-gray-500 mb-1">Event Data</h4>
                      <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-40">
                        {JSON.stringify(event.data, null, 2)}
                      </pre>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => handleEvaluate(event.id)}
                      disabled={runEval.isPending}
                    >
                      <PlayIcon className="h-3 w-3 mr-1" />
                      {runEval.isPending ? "Evaluating..." : "Evaluate"}
                    </Button>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        )}

        {selectedTab === "runs" && (
          <div className="space-y-4">
            {loadingOutputs && (
              <div className="flex items-center justify-center py-8">
                <Loader2Icon className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            )}

            {!loadingOutputs && (!evalOutputs || evalOutputs.length === 0) && (
              <p className="text-center text-gray-500 py-8">No evaluation runs found</p>
            )}

            {evalOutputs?.map((output) => (
              <Card key={output.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-mono">
                      {output.id.substring(0, 8)}...
                    </CardTitle>
                    <StatusBadge status={output.output.status} />
                  </div>
                  <CardDescription className="text-xs">
                    {new Date(output.created_at).toLocaleString()} •{" "}
                    {(output.output.elapsed_ns / 1_000_000).toFixed(2)}ms
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {output.output.exec_info.map((info, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between text-xs border-b pb-2"
                      >
                        <span className="font-mono">{info.node_id}</span>
                        <StatusBadge status={info.status} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
