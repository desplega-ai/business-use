import { useState } from "react";
import { apiClient } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

interface ApiSetupProps {
  onConfigured: () => void;
}

export function ApiSetup({ onConfigured }: ApiSetupProps) {
  const [apiKey, setApiKey] = useState("");
  const [apiUrl, setApiUrl] = useState("http://localhost:13370");
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsChecking(true);

    try {
      apiClient.setConfig({ apiKey, apiUrl });
      const isConnected = await apiClient.checkConnection();

      if (isConnected) {
        onConfigured();
      } else {
        setError("Failed to connect to API. Please check your API key and URL.");
        apiClient.clearConfig();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      apiClient.clearConfig();
    } finally {
      setIsChecking(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>API Configuration</CardTitle>
          <CardDescription>Enter your API credentials to connect to the backend</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="apiKey">API Key *</Label>
              <Input
                id="apiKey"
                type="text"
                placeholder="Enter your API key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiUrl">API URL</Label>
              <Input
                id="apiUrl"
                type="url"
                placeholder="http://localhost:13370"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                required
              />
              <p className="text-xs text-gray-500">Default: http://localhost:13370</p>
            </div>

            {error && (
              <div className="p-3 rounded-md bg-red-50 border border-red-200">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            <Button type="submit" disabled={isChecking} className="w-full">
              {isChecking ? "Connecting..." : "Connect"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
