import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./api";

export function useNodes() {
  const config = apiClient.getConfig();

  return useQuery({
    queryKey: ["nodes"],
    queryFn: () => apiClient.getNodes(),
    enabled: !!config,
  });
}

export function useEvents(flow?: string, node_id?: string, limit = 100, offset = 0) {
  return useQuery({
    queryKey: ["events", flow, node_id, limit, offset],
    queryFn: () => apiClient.getEvents({ flow, node_id, limit, offset }),
    enabled: !!flow || !!node_id,
  });
}

export function useEvalOutputs(name?: string[], ev_id?: string, limit = 100, offset = 0) {
  return useQuery({
    queryKey: ["eval-outputs", name, ev_id, limit, offset],
    queryFn: () => apiClient.getEvalOutputs({ name, ev_id, limit, offset }),
  });
}

export function useRunEval() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: {
      ev_id?: string;
      whole_graph?: boolean;
      run_id?: string;
      flow?: string;
      start_node_id?: string;
    }) => apiClient.runEval(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["eval-outputs"] });
    },
  });
}
