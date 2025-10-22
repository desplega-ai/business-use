# Testing the Ensure Command

This guide walks through testing the `flow ensure` command locally.

## Setup

1. **Initialize the project**:
```bash
cd core
uv sync
uv run business-use init
```

2. **Create secrets file** (optional, for real API testing):
```bash
cp .business-use/secrets.yaml.example .business-use/secrets.yaml
# Edit and add your API keys
```

3. **Sync flow definitions to database**:
```bash
uv run business-use nodes sync
```

4. **Start the development server** (in another terminal):
```bash
uv run business-use server dev --reload
```

## Testing Scenarios

### Scenario 1: Test with Seed Script (Dummy Events)

This tests the flow evaluation without actually executing triggers.

```bash
# 1. Send dummy events for a specific run_id
uv run python scripts/seed_test.py payment_12345

# 2. Manually evaluate the run
uv run business-use flow eval payment_12345 payment_approval --verbose
```

Expected: Should show passed/failed status for the flow nodes.

### Scenario 2: Test Ensure Command (No Real API)

Since the example flow requires a real API endpoint, you'll need to either:

**Option A: Mock API Server**

Create a simple mock server for testing:

```python
# mock_api.py
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.post("/payments")
async def create_payment():
    return {
        "data": {
            "payment_id": "payment_test_123",
            "status": "created",
            "amount": 100
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Then update secrets:
```yaml
# .business-use/secrets.yaml
API_BASE_URL: "http://localhost:8000"
PAYMENT_API_KEY: "test_key"
```

Run the mock server in another terminal:
```bash
python mock_api.py
```

Now test ensure:
```bash
uv run business-use flow ensure payment_approval --live
```

**Option B: Update Flow for Command Trigger**

Edit `.business-use/payment_approval.yaml` to use a bash command instead:

```yaml
flow: payment_approval
nodes:
  - id: create_payment
    type: trigger
    handler: command
    handler_input:
      params:
        command: 'echo {"payment_id":"payment_test_123"}'
        run_id_extractor:
          engine: python
          script: 'import json; output["stdout"].strip() and json.loads(output["stdout"])["payment_id"]'

  - id: payment_confirmed
    type: act
    dep_ids: [create_payment]
    conditions:
      - timeout_ms: 30000

  - id: receipt_sent
    type: assert
    dep_ids: [payment_confirmed]
    validator:
      engine: python
      script: "data.get('receipt_sent') == True"
```

Then:
```bash
# Sync updated flow
uv run business-use nodes sync

# Run ensure
uv run business-use flow ensure payment_approval --live
```

### Scenario 3: Test with Real API

If you have a real API endpoint:

1. Update `.business-use/payment_approval.yaml` with your API URL
2. Add credentials to `.business-use/secrets.yaml`
3. Run ensure:

```bash
uv run business-use flow ensure payment_approval --live
```

## Expected Output

```bash
$ uv run business-use flow ensure payment_approval --live

============================================================
Flow Ensure - Execute & Verify
============================================================

[1/5] Checking workspace...
  ✓ Workspace: ./.business-use

[2/5] Checking sync status...

[3/5] Running flow: payment_approval

[4/5] Executing triggers (concurrency: 1)...

[5/5] Results
  [00:02.1s] ✓ payment_approval: passed

============================================================
Summary
============================================================
  Flows: 1
  ✓ Passed: 1
  Total time: 2.1s
============================================================
```

## Debugging

If something goes wrong:

1. **Check logs**: The CLI shows INFO/ERROR logs by default
2. **Verbose mode**: Add `--verbose` to eval commands
3. **Show graph**: `uv run business-use flow graph payment_approval`
4. **Check nodes**: `uv run business-use nodes validate`
5. **View runs**: `uv run business-use flow runs --flow payment_approval`

## Common Issues

### "No flows with trigger nodes found"
- Make sure you ran `uv run business-use nodes sync`
- Check that your YAML has a node with `type: trigger`

### "Secret 'XXX' not found"
- Create `.business-use/secrets.yaml` from the example
- Make sure the secret key matches (case-sensitive)

### "Environment variable 'XXX' not set"
- Export the variable: `export XXX=value`
- Or add it to `.business-use/secrets.yaml` and use `${secret.XXX}`

### "Trigger node cannot have dependencies"
- Trigger nodes must be root nodes (no `dep_ids`)
- Check your YAML flow definition

### HTTP request fails (401, 403, etc.)
- Check your API credentials in secrets.yaml
- Verify the Authorization header format
- Test the API endpoint manually with curl first
