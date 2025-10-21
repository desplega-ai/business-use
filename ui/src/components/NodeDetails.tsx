import { useState, useEffect, useCallback } from "react";
import { Node, BaseEvalItemOutput, EvalStatus } from "../lib/types";
import { useEvents, useEvalOutputs, useRunEval } from "../lib/queries";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { ScrollArea } from "./ui/scroll-area";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { PlayIcon, Loader2Icon, EyeIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";

interface NodeDetailsProps {
  node: Node | null;
  onEvalInfoChange?: (evalInfo: BaseEvalItemOutput[] | undefined) => void;
  onNodeSelect?: (node: Node) => void;
  allNodes?: Node[];
}

function getStatusVariant(
  status: EvalStatus
): "success" | "error" | "warning" | "secondary" | "default" {
  switch (status) {
    case "passed":
      return "success";
    case "failed":
    case "error":
    case "timed_out":
      return "error";
    case "running":
      return "default";
    case "pending":
    case "skipped":
      return "secondary";
    default:
      return "secondary";
  }
}

export function NodeDetails({ node, onEvalInfoChange, onNodeSelect, allNodes }: NodeDetailsProps) {
  const [selectedTab, setSelectedTab] = useState<"details" | "events" | "runs">("details");
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [viewedEvalId, setViewedEvalId] = useState<string | null>(null);
  const [eventsPage, setEventsPage] = useState(0);
  const [runsPage, setRunsPage] = useState(0);
  const pageSize = 10;

  const { data: events, isLoading: loadingEvents } = useEvents(
    node?.flow,
    node?.id,
    pageSize,
    eventsPage * pageSize
  );

  const { data: evalOutputs, isLoading: loadingOutputs } = useEvalOutputs(
    node ? [node.flow] : undefined,
    undefined,
    pageSize,
    runsPage * pageSize
  );

  const runEval = useRunEval();

  const handleEvaluate = (event: { id: string; run_id: string; flow: string }) => {
    // Use new API format (preferred)
    runEval.mutate({
      run_id: event.run_id,
      flow: event.flow,
      start_node_id: node?.id, // Start from the current node
    });
  };

  const handleToggleViewEval = useCallback(
    (evalId: string, evalInfo: BaseEvalItemOutput[]) => {
      if (viewedEvalId === evalId) {
        // Clear the view
        onEvalInfoChange?.(undefined);
        setViewedEvalId(null);
      } else {
        // Set the view
        onEvalInfoChange?.(evalInfo);
        setViewedEvalId(evalId);
      }
    },
    [viewedEvalId, onEvalInfoChange]
  );

  const handleClearEval = useCallback(() => {
    onEvalInfoChange?.(undefined);
    setViewedEvalId(null);
  }, [onEvalInfoChange]);

  // Reset pagination when node changes
  useEffect(() => {
    setEventsPage(0);
    setRunsPage(0);
    setExpandedEventId(null);
    setExpandedRunId(null);
    handleClearEval();
  }, [node, handleClearEval]);

  if (!node) {
    return (
      <div className="p-6 h-full flex items-center justify-center text-gray-500">
        <p>Select a node to view details</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <Tabs
        value={selectedTab}
        onValueChange={(v) => setSelectedTab(v as "details" | "events" | "runs")}
      >
        <div className="border-b px-4 pt-4">
          <TabsList className="w-full">
            <TabsTrigger value="details" active={selectedTab === "details"} className="flex-1">
              Details
            </TabsTrigger>
            <TabsTrigger value="events" active={selectedTab === "events"} className="flex-1">
              Events
            </TabsTrigger>
            <TabsTrigger value="runs" active={selectedTab === "runs"} className="flex-1">
              Runs
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="details">
          <ScrollArea className="flex-1" maxHeight="calc(100vh - 180px)">
            <div className="p-6 space-y-4">
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
          </ScrollArea>
        </TabsContent>

        <TabsContent value="events">
          <ScrollArea className="flex-1" maxHeight="calc(100vh - 180px)">
            <div className="p-6 space-y-4">
              {loadingEvents && (
                <div className="flex items-center justify-center py-8">
                  <Loader2Icon className="h-6 w-6 animate-spin text-gray-400" />
                </div>
              )}

              {!loadingEvents && (!events || events.length === 0) && (
                <p className="text-center text-gray-500 py-8">No events found</p>
              )}

              {events && events.length > 0 && (
                <div className="space-y-4">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Event ID</TableHead>
                        <TableHead>Run ID</TableHead>
                        <TableHead>Timestamp</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {events.map((event) => (
                        <TableRow
                          key={event.id}
                          className="cursor-pointer hover:bg-gray-50"
                          onClick={() =>
                            setExpandedEventId(expandedEventId === event.id ? null : event.id)
                          }
                        >
                          <TableCell className="font-mono text-xs">
                            {event.id.substring(0, 8)}...
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {event.run_id.substring(0, 8)}...
                          </TableCell>
                          <TableCell className="text-xs">
                            {new Date(event.ts / 1_000_000).toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEvaluate(event);
                              }}
                              disabled={runEval.isPending}
                            >
                              <PlayIcon className="h-3 w-3 mr-1" />
                              Eval
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  {expandedEventId && events.find((e) => e.id === expandedEventId) && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Event Data</CardTitle>
                        <CardDescription className="font-mono text-xs">
                          {expandedEventId}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-60">
                          {JSON.stringify(
                            events.find((e) => e.id === expandedEventId)?.data,
                            null,
                            2
                          )}
                        </pre>
                      </CardContent>
                    </Card>
                  )}

                  <div className="flex items-center justify-between pt-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setEventsPage((p) => Math.max(0, p - 1))}
                      disabled={eventsPage === 0}
                    >
                      Previous
                    </Button>
                    <span className="text-xs text-gray-500">Page {eventsPage + 1}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setEventsPage((p) => p + 1)}
                      disabled={!events || events.length < pageSize}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="runs">
          <ScrollArea className="flex-1" maxHeight="calc(100vh - 180px)">
            <div className="p-6 space-y-4">
              {loadingOutputs && (
                <div className="flex items-center justify-center py-8">
                  <Loader2Icon className="h-6 w-6 animate-spin text-gray-400" />
                </div>
              )}

              {!loadingOutputs && (!evalOutputs || evalOutputs.length === 0) && (
                <p className="text-center text-gray-500 py-8">No evaluation runs found</p>
              )}

              {evalOutputs && evalOutputs.length > 0 && (
                <div className="space-y-4">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Run ID</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Time</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {evalOutputs.map((output) => (
                        <>
                          <TableRow
                            key={output.id}
                            className="cursor-pointer hover:bg-gray-50"
                            onClick={() =>
                              setExpandedRunId(expandedRunId === output.id ? null : output.id)
                            }
                          >
                            <TableCell className="font-mono text-xs">
                              <div className="flex items-center gap-2">
                                {expandedRunId === output.id ? (
                                  <ChevronUpIcon className="h-3 w-3" />
                                ) : (
                                  <ChevronDownIcon className="h-3 w-3" />
                                )}
                                {output.id.substring(0, 8)}...
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant={getStatusVariant(output.output.status)}>
                                {output.output.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs">
                              {(output.output.elapsed_ns / 1_000_000).toFixed(2)}ms
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                size="sm"
                                variant={viewedEvalId === output.id ? "default" : "outline"}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleToggleViewEval(output.id, output.output.exec_info);
                                }}
                              >
                                <EyeIcon className="h-3 w-3 mr-1" />
                                {viewedEvalId === output.id ? "Hide" : "View"}
                              </Button>
                            </TableCell>
                          </TableRow>
                          {expandedRunId === output.id && (
                            <TableRow key={`${output.id}-details`}>
                              <TableCell colSpan={4} className="bg-gray-50">
                                <div className="py-2 space-y-2">
                                  <div className="text-xs text-gray-500">
                                    {new Date(output.created_at).toLocaleString()}
                                  </div>
                                  <Table>
                                    <TableHeader>
                                      <TableRow>
                                        <TableHead className="text-xs">Node</TableHead>
                                        <TableHead className="text-xs">Status</TableHead>
                                        <TableHead className="text-right text-xs">
                                          Time (ms)
                                        </TableHead>
                                      </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                      {output.output.exec_info.map((info, idx) => {
                                        const nodeForInfo = allNodes?.find(
                                          (n) => n.id === info.node_id
                                        );
                                        return (
                                          <TableRow
                                            key={idx}
                                            className={
                                              nodeForInfo && onNodeSelect
                                                ? "cursor-pointer hover:bg-gray-100"
                                                : ""
                                            }
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              if (nodeForInfo && onNodeSelect) {
                                                onNodeSelect(nodeForInfo);
                                              }
                                            }}
                                          >
                                            <TableCell className="font-mono text-xs">
                                              {info.node_id}
                                            </TableCell>
                                            <TableCell>
                                              <Badge variant={getStatusVariant(info.status)}>
                                                {info.status}
                                              </Badge>
                                            </TableCell>
                                            <TableCell className="text-right text-xs">
                                              {(info.elapsed_ns / 1_000_000).toFixed(2)}
                                            </TableCell>
                                          </TableRow>
                                        );
                                      })}
                                    </TableBody>
                                  </Table>
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="flex items-center justify-between pt-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setRunsPage((p) => Math.max(0, p - 1))}
                      disabled={runsPage === 0}
                    >
                      Previous
                    </Button>
                    <span className="text-xs text-gray-500">Page {runsPage + 1}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setRunsPage((p) => p + 1)}
                      disabled={!evalOutputs || evalOutputs.length < pageSize}
                    >
                      Next
                    </Button>
                  </div>

                  {onEvalInfoChange && (
                    <Button size="sm" variant="ghost" onClick={handleClearEval} className="w-full">
                      Clear Graph Highlight
                    </Button>
                  )}
                </div>
              )}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
