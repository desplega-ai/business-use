import { ApiConfig, Node, Event, EvalOutput, BaseEvalOutput } from "./types";

class ApiClient {
  private config: ApiConfig | null = null;

  setConfig(config: ApiConfig) {
    this.config = config;
    localStorage.setItem("apiConfig", JSON.stringify(config));
  }

  getConfig(): ApiConfig | null {
    if (this.config) return this.config;

    const stored = localStorage.getItem("apiConfig");
    if (stored) {
      this.config = JSON.parse(stored);
      return this.config;
    }

    return null;
  }

  clearConfig() {
    this.config = null;
    localStorage.removeItem("apiConfig");
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const config = this.getConfig();
    if (!config) {
      throw new Error("API not configured");
    }

    const url = `${config.apiUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      "X-API-Key": config.apiKey,
      ...options.headers,
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} - ${error}`);
    }

    return response.json();
  }

  async checkConnection(): Promise<boolean> {
    try {
      await this.request("/v1/status");
      return true;
    } catch {
      return false;
    }
  }

  async getNodes(): Promise<Node[]> {
    return this.request<Node[]>("/v1/nodes");
  }

  async getEvents(params: {
    flow?: string;
    node_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<Event[]> {
    const query = new URLSearchParams();
    if (params.flow) query.append("flow", params.flow);
    if (params.node_id) query.append("node_id", params.node_id);
    if (params.limit) query.append("limit", params.limit.toString());
    if (params.offset) query.append("offset", params.offset.toString());

    return this.request<Event[]>(`/v1/events?${query.toString()}`);
  }

  async getEvalOutputs(params: {
    name?: string[];
    ev_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<EvalOutput[]> {
    const query = new URLSearchParams();
    if (params.name) {
      params.name.forEach((n) => query.append("name", n));
    }
    if (params.ev_id) query.append("ev_id", params.ev_id);
    if (params.limit) query.append("limit", params.limit.toString());
    if (params.offset) query.append("offset", params.offset.toString());

    return this.request<EvalOutput[]>(`/v1/eval-outputs?${query.toString()}`);
  }

  async runEval(params: {
    ev_id?: string;
    whole_graph?: boolean;
    run_id?: string;
    flow?: string;
    start_node_id?: string;
  }): Promise<BaseEvalOutput> {
    return this.request<BaseEvalOutput>("/v1/run-eval", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }
}

export const apiClient = new ApiClient();
