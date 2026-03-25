/**
 * E2E test orchestrator for Business-Use.
 *
 * Spins up an isolated server with a temp DB, runs scan + SDK fixtures,
 * and verifies both passing and failing flow evaluations.
 *
 * Usage: bun run e2e/run.ts
 */

import { mkdtempSync, writeFileSync, rmSync, existsSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { execSync, spawn, type ChildProcess } from "child_process";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const API_KEY = "test-e2e-key";
const PORT = 13399;
const BASE_URL = `http://localhost:${PORT}`;
const ROOT = join(import.meta.dirname, "..");
const CORE = join(ROOT, "core");
const FIXTURES_PY = join(ROOT, "e2e", "fixtures", "python");
const FIXTURES_TS = join(ROOT, "e2e", "fixtures", "typescript");
const SDK_JS = join(ROOT, "sdk-js");

// ---------------------------------------------------------------------------
// Fail-safe cleanup state
// ---------------------------------------------------------------------------

let serverProc: ChildProcess | null = null;
let tmpDir: string | null = null;
let exitCode = 0;

async function cleanup() {
  log("cleanup", "Cleaning up...");

  if (serverProc) {
    log("cleanup", "Stopping server (SIGTERM)...");
    serverProc.kill("SIGTERM");

    // Wait up to 3s for graceful shutdown, then SIGKILL
    const killed = await Promise.race([
      new Promise<boolean>((resolve) => {
        serverProc!.on("exit", () => resolve(true));
      }),
      new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 3000)),
    ]);

    if (!killed) {
      log("cleanup", "Server didn't stop, sending SIGKILL...");
      serverProc.kill("SIGKILL");
    }
    serverProc = null;
  }

  if (tmpDir) {
    log("cleanup", `Removing temp dir: ${tmpDir}`);
    rmSync(tmpDir, { recursive: true, force: true });
    tmpDir = null;
  }

  log("cleanup", "Done.");
}

// Catch all exit paths
process.on("SIGINT", async () => {
  await cleanup();
  process.exit(130);
});
process.on("SIGTERM", async () => {
  await cleanup();
  process.exit(143);
});
process.on("uncaughtException", async (err) => {
  console.error("\n[FATAL] Uncaught exception:", err);
  await cleanup();
  process.exit(1);
});
process.on("unhandledRejection", async (err) => {
  console.error("\n[FATAL] Unhandled rejection:", err);
  await cleanup();
  process.exit(1);
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function log(phase: string, msg: string) {
  const tag = phase.padEnd(8);
  console.log(`[${tag}] ${msg}`);
}

function run(cmd: string, opts: { cwd?: string; env?: Record<string, string> } = {}) {
  const mergedEnv = { ...process.env, ...opts.env };
  try {
    execSync(cmd, {
      cwd: opts.cwd ?? ROOT,
      env: mergedEnv,
      stdio: "pipe",
      timeout: 60_000,
    });
  } catch (e: any) {
    const stderr = e.stderr?.toString() ?? "";
    const stdout = e.stdout?.toString() ?? "";
    throw new Error(`Command failed: ${cmd}\nstdout: ${stdout}\nstderr: ${stderr}`);
  }
}

async function waitForServer(maxWaitMs = 15_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    try {
      const res = await fetch(`${BASE_URL}/health`);
      if (res.ok) return;
    } catch {
      // Server not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Server did not become ready within ${maxWaitMs}ms`);
}

async function apiGet(path: string): Promise<any> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "X-Api-Key": API_KEY },
  });
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status} ${await res.text()}`);
  return res.json();
}

async function apiPost(path: string, body: any): Promise<any> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "X-Api-Key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status} ${await res.text()}`);
  return res.json();
}

function assertEqual(actual: any, expected: any, label: string) {
  if (actual !== expected) {
    throw new Error(`Assertion failed [${label}]: expected "${expected}", got "${actual}"`);
  }
}

// ---------------------------------------------------------------------------
// Phases
// ---------------------------------------------------------------------------

async function setup() {
  // Create temp dir for isolated DB
  tmpDir = mkdtempSync(join(tmpdir(), "business-use-e2e-"));
  const dbPath = join(tmpDir, "db.sqlite");
  log("setup", `Temp dir: ${tmpDir}`);

  const envVars = {
    BUSINESS_USE_API_KEY: API_KEY,
    BUSINESS_USE_DATABASE_PATH: dbPath,
    BUSINESS_USE_LOG_LEVEL: "warning",
  };

  // Run migrations
  log("setup", "Running migrations...");
  run(`uv run business-use db migrate`, { cwd: CORE, env: envVars });

  // Build sdk-js (fixtures need dist/)
  if (!existsSync(join(SDK_JS, "node_modules"))) {
    log("setup", "Installing sdk-js deps...");
    run(`pnpm install`, { cwd: SDK_JS });
  }
  log("setup", "Building sdk-js...");
  run(`pnpm build`, { cwd: SDK_JS });

  // Install fixture deps (if needed)
  if (!existsSync(join(FIXTURES_TS, "node_modules"))) {
    log("setup", "Installing TS fixture deps...");
    run(`pnpm install`, { cwd: FIXTURES_TS });
  }
  if (!existsSync(join(FIXTURES_PY, ".venv"))) {
    log("setup", "Installing Python fixture deps...");
    run(`uv sync`, { cwd: FIXTURES_PY });
  }

  // Start server
  log("setup", `Starting server on port ${PORT}...`);
  serverProc = spawn("uv", ["run", "business-use", "server", "dev", "--port", String(PORT)], {
    cwd: CORE,
    env: { ...process.env, ...envVars },
    stdio: "pipe",
  });

  serverProc.on("error", (err) => {
    console.error("[server] Spawn error:", err);
  });

  // Wait for ready
  await waitForServer();
  log("setup", "Server ready!");
}

async function testScan() {
  const env = {
    BUSINESS_USE_API_KEY: API_KEY,
    BUSINESS_USE_DATABASE_PATH: join(tmpDir!, "db.sqlite"),
  };

  log("scan", "Scanning TypeScript fixtures...");
  run(
    `uv run business-use scan ${FIXTURES_TS} --url ${BASE_URL} --api-key ${API_KEY}`,
    { cwd: CORE, env },
  );

  log("scan", "Scanning Python fixtures...");
  run(
    `uv run business-use scan ${FIXTURES_PY} --url ${BASE_URL} --api-key ${API_KEY}`,
    { cwd: CORE, env },
  );

  // Verify nodes exist
  log("scan", "Verifying nodes via API...");
  const nodesRes = await apiGet("/v1/nodes");
  const nodes: any[] = nodesRes.data ?? nodesRes;
  const checkoutNodes = nodes.filter((n: any) => n.flow === "checkout");
  const nodeIds = checkoutNodes.map((n: any) => n.id).sort();

  log("scan", `Found ${checkoutNodes.length} checkout nodes: ${nodeIds.join(", ")}`);

  const expected = ["cart_created", "inventory_reserved", "order_confirmed", "payment_processed"];
  for (const id of expected) {
    if (!nodeIds.includes(id)) {
      throw new Error(`Scan verification failed: missing node "${id}"`);
    }
  }
  log("scan", "All expected nodes found!");
}

async function runFixture(
  label: string,
  cmd: string,
  cwd: string,
  runId: string,
) {
  log("run", `${label} (run_id=${runId})...`);
  run(cmd, {
    cwd,
    env: {
      E2E_RUN_ID: runId,
      BUSINESS_USE_API_KEY: API_KEY,
      BUSINESS_USE_URL: BASE_URL,
    },
  });
  log("run", `${label} done.`);
}

async function testRunFlows() {
  // Pass flows
  await runFixture("TS pass flow", "npx tsx pass_flow.ts", FIXTURES_TS, "ts_pass_001");
  await runFixture("PY pass flow", "uv run python pass_flow.py", FIXTURES_PY, "py_pass_001");

  // Fail flows
  await runFixture("TS fail flow", "npx tsx fail_flow.ts", FIXTURES_TS, "ts_fail_001");
  await runFixture("PY fail flow", "uv run python fail_flow.py", FIXTURES_PY, "py_fail_001");
}

async function testEvaluations() {
  const cases: Array<{ runId: string; expectedStatus: string }> = [
    { runId: "ts_pass_001", expectedStatus: "passed" },
    { runId: "py_pass_001", expectedStatus: "passed" },
    { runId: "ts_fail_001", expectedStatus: "failed" },
    { runId: "py_fail_001", expectedStatus: "failed" },
  ];

  for (const { runId, expectedStatus } of cases) {
    log("eval", `Evaluating ${runId}...`);
    const result = await apiPost("/v1/run-eval", { run_id: runId, flow: "checkout" });

    const status = result.output?.status ?? result.status;
    assertEqual(status, expectedStatus, `${runId} status`);
    log("eval", `${runId}: ${status} ${status === expectedStatus ? "OK" : "FAIL"}`);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

try {
  console.log("=".repeat(60));
  console.log("Business-Use E2E Tests");
  console.log("=".repeat(60));

  await setup();
  await testScan();        // Scan first — creates nodes with source="scan"
  await testRunFlows();    // SDK events upgrade scan nodes to source="code" with validators
  await testEvaluations(); // Verify outcomes

  console.log("\n" + "=".repeat(60));
  console.log("All E2E tests passed!");
  console.log("=".repeat(60));
} catch (err: any) {
  console.error("\n[FAIL]", err.message ?? err);
  exitCode = 1;
} finally {
  await cleanup();
  process.exit(exitCode);
}
