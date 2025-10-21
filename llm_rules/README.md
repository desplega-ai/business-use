# LLM Integration Guide for Business-Use

This directory contains configuration files and guides for integrating Business-Use SDK knowledge into various AI coding assistants.

## Available Files

- **`sdk-usage.md`**: Comprehensive guide teaching LLMs how to use the Business-Use SDK
- **`cursor-rules.md`**: Quick reference rules for Cursor AI integration
- **`auto-instrument.md`**: Template for creating an auto-instrumentation command (for Claude Code)

## Integration by Tool

### 🤖 Claude Code

**Location**: `.claude/commands/`

**Setup**:
1. Copy `auto-instrument.md` to `.claude/commands/auto-instrument.md`
2. Use the slash command: `/auto-instrument`

**How it works**:
- Claude Code automatically discovers Markdown files in `.claude/commands/`
- Each file becomes a slash command (filename = command name)
- Commands can use `$ARGUMENTS` for parameters
- Commands are project-scoped (checked into git)

**Example**:
```bash
# In your project
mkdir -p .claude/commands
cp llm_rules/auto-instrument.md .claude/commands/

# Then in Claude Code
/auto-instrument
```

**Additional configuration**:
You can also add general Business-Use knowledge to Claude Code's context by:
1. Using the `@` mention feature to reference `llm_rules/sdk-usage.md`
2. Adding project-wide context in `.claude/project.md` (if available)

**Resources**:
- [Claude Code Slash Commands Docs](https://docs.claude.com/en/docs/claude-code/slash-commands)
- [Awesome Claude Code Commands](https://github.com/hesreallyhim/awesome-claude-code)

---

### 🔵 Cursor AI

**Location**: `.cursorrules` or `.cursor/rules/`

**Setup (Legacy .cursorrules)**:
1. Create `.cursorrules` in project root:
```bash
cat llm_rules/cursor-rules.md > .cursorrules
```

**Setup (New Rules System - Recommended)**:
1. Create `.cursor/rules/business-use.mdc`:
```bash
mkdir -p .cursor/rules
cat llm_rules/cursor-rules.md > .cursor/rules/business-use.mdc
```

2. In Cursor, go to Settings → Rules for AI → Add Project Rule
3. Select "Always" rule type

**How it works**:
- Cursor reads `.cursorrules` or `.cursor/rules/*.mdc` files
- Rules apply to all AI interactions (chat, autocomplete, inline edit)
- Multiple rule files can be combined
- Rules are automatically included in AI context

**Combining rules**:
```bash
# Option 1: Merge into .cursorrules
cat llm_rules/cursor-rules.md llm_rules/sdk-usage.md > .cursorrules

# Option 2: Use .cursor/rules/ for granular control
mkdir -p .cursor/rules
cp llm_rules/cursor-rules.md .cursor/rules/quick-reference.mdc
cp llm_rules/sdk-usage.md .cursor/rules/detailed-guide.mdc
```

**Resources**:
- [Cursor Rules Documentation](https://docs.cursor.com/context/rules)
- [Awesome Cursorrules](https://github.com/PatrickJS/awesome-cursorrules)
- [Cursor Rules Generator](https://cursorrules.org/)

---

### 🐙 GitHub Copilot

**Location**: `.github/copilot-instructions.md`

**Setup**:
```bash
mkdir -p .github
cat llm_rules/sdk-usage.md > .github/copilot-instructions.md
```

**Advanced Setup (Scoped Instructions - 2025)**:

GitHub Copilot now supports scoped instructions using `.github/instructions/*.instructions.md`:

```bash
mkdir -p .github/instructions

# Create service-specific instructions
cat > .github/instructions/services.instructions.md << 'EOF'
---
applies_to:
  - "src/services/**"
  - "src/domain/**"
---

When working with service layer code, use Business-Use SDK to track business flows.

$(cat llm_rules/cursor-rules.md)
EOF
```

**How it works**:
- Copilot reads `.github/copilot-instructions.md` for repository-wide context
- Instructions are included in all Copilot Chat requests
- Scoped `.instructions.md` files apply to specific directories
- Instructions appear in "References" section of Copilot responses

**Best practices**:
- Keep instructions concise (GitHub recommends short, self-contained statements)
- Don't reference external URLs (not supported)
- Include: tech stack, coding guidelines, project structure
- For Business-Use: Include when to use, integration patterns, common flows

**Example `.github/copilot-instructions.md`**:
```markdown
# Project Context

This project uses Business-Use SDK to track and validate critical business flows.

## Tech Stack
- Backend: Python/FastAPI or Node/Express
- Flow Tracking: Business-Use SDK

## Business-Use Integration

### When to Suggest
- Multi-step business processes (checkout, onboarding, publishing)
- Critical user journeys that need validation
- Operations with ordering dependencies

### How to Use
Use the unified `ensure()` function:
- Without `validator` → creates action node
- With `validator` → creates assertion node

### Example
\`\`\`python
from business_use import ensure

ensure(
    id="order_created",
    flow="checkout",
    run_id=order_id,
    data={"amount": 100}
)
\`\`\`

See llm_rules/sdk-usage.md for complete guide.
```

**Resources**:
- [GitHub Copilot Instructions Docs](https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot)
- [5 Tips for Better Instructions](https://github.blog/ai-and-ml/github-copilot/5-tips-for-writing-better-custom-instructions-for-copilot/)
- [Awesome Copilot Customizations](https://developer.microsoft.com/blog/introducing-awesome-github-copilot-customizations-repo)

---

### 🤝 Aider

**Location**: Project root or `~/.aider/`

**Setup (Project-specific)**:
```bash
# Option 1: Use CONVENTIONS.md
cat llm_rules/cursor-rules.md > CONVENTIONS.md

# Option 2: Use --read parameter with custom files
mkdir -p .aider
cp llm_rules/sdk-usage.md .aider/business-use-guide.md
```

**Usage**:
```bash
# Include Business-Use guide in every session
aider --read .aider/business-use-guide.md

# Or add to .aider.conf.yml
cat > .aider.conf.yml << 'EOF'
read:
  - .aider/business-use-guide.md
  - CONVENTIONS.md
EOF

# Then just run
aider
```

**How it works**:
- `CONVENTIONS.md`: Automatically read by Aider as coding conventions
- `--read` parameter: Includes files as read-only context (uses prompt caching)
- `.aider.conf.yml`: Persistent configuration for project
- Files in `--read` are cached and cost-efficient

**Best practices**:
- Use `CONVENTIONS.md` for quick rules and patterns
- Use `--read` for detailed guides that don't change often
- Combine both for comprehensive context

**Resources**:
- [Aider Documentation](https://aider.chat/docs/)
- [Configuration Guide](https://aider.chat/docs/config.html)
- [CONVENTIONS.md Usage](https://aider.chat/docs/usage.html#conventions)

---

### 🌟 Continue.dev

**Location**: `.continuerules` or Continue config

**Setup**:
```bash
# Create .continuerules
cat llm_rules/cursor-rules.md > .continuerules
```

**How it works**:
- Similar to Cursor's `.cursorrules`
- Automatically included in AI context
- Applies to all Continue interactions

**Resources**:
- [Continue.dev Documentation](https://continue.dev/docs)

---

### 🔮 Cline (formerly Claude Dev)

**Location**: Project-specific instructions

**Setup**:
Create a `CLAUDE_INSTRUCTIONS.md` in your project root:
```bash
cat llm_rules/sdk-usage.md > CLAUDE_INSTRUCTIONS.md
```

**Usage**:
Reference the file in your Cline conversations:
```
@CLAUDE_INSTRUCTIONS.md

Help me add Business-Use tracking to the checkout flow
```

---

### 🧠 Amazon CodeWhisperer

**Location**: Code comments and documentation

**Setup**:
CodeWhisperer learns from comments and existing code patterns. Add Business-Use patterns to your codebase:

```python
# Example: services/example.py
"""
This service uses Business-Use SDK to track critical business flows.
Always use ensure() to track key events in the service layer.
"""

from business_use import ensure

def example_operation(id: str):
    # Track business event with Business-Use
    ensure(
        id="operation_completed",
        flow="example_flow",
        run_id=id,
        data={"status": "success"}
    )
```

---

### 🦾 Tabnine

**Location**: Team settings or code patterns

**Setup**:
Tabnine learns from your codebase. Create example files showing Business-Use patterns:

```bash
mkdir -p .tabnine/examples
cp examples/python-simple.py .tabnine/examples/
cp examples/javascript-simple.js .tabnine/examples/
```

Add to `.tabnine/tabnine.yml`:
```yaml
team_learning:
  enabled: true
  include:
    - "**/*.py"
    - "**/*.js"
    - "**/*.ts"
```

---

## General Strategy for Any LLM Tool

If your tool isn't listed above, use this general approach:

### 1. **Project Documentation**
Create a `docs/business-use-integration.md`:
```bash
mkdir -p docs
cp llm_rules/sdk-usage.md docs/business-use-integration.md
```

Then reference it in conversations:
```
@docs/business-use-integration.md

Help me add Business-Use tracking
```

### 2. **Code Examples**
Maintain example files that LLMs can learn from:
```bash
examples/
  ├── python-simple.py          # Basic Python example
  ├── javascript-simple.js      # Basic JS example
  └── advanced-patterns.md      # Advanced usage patterns
```

### 3. **Inline Comments**
Add explanatory comments in your code:
```python
from business_use import ensure

# Business-Use: Track order creation as the start of checkout flow
ensure(id="order_created", flow="checkout", run_id=order_id, data={...})
```

### 4. **README Section**
Add a section to your project README:
```markdown
## Flow Tracking

This project uses Business-Use SDK to track and validate business flows.
See `llm_rules/sdk-usage.md` for integration guidelines.
```

---

## Quick Start for New Projects

1. **Copy LLM rules to your project**:
```bash
mkdir -p llm_rules
cp -r /path/to/business-use/llm_rules/* llm_rules/
```

2. **Set up for your preferred tool** (choose one or more):

**Claude Code**:
```bash
mkdir -p .claude/commands
cp llm_rules/auto-instrument.md .claude/commands/
```

**Cursor**:
```bash
cat llm_rules/cursor-rules.md > .cursorrules
```

**GitHub Copilot**:
```bash
mkdir -p .github
cat llm_rules/sdk-usage.md > .github/copilot-instructions.md
```

**Aider**:
```bash
cat llm_rules/cursor-rules.md > CONVENTIONS.md
```

3. **Commit to git**:
```bash
git add llm_rules/ .cursorrules .claude/ .github/
git commit -m "Add Business-Use LLM integration"
```

---

## Testing Your Integration

After setting up, test that your LLM tool recognizes Business-Use:

### Test with a question:
```
How do I track a checkout flow with Business-Use?
```

Expected response should include:
- Use of `ensure()` function
- Proper flow structure with `run_id`
- Validators for business rules
- Dependencies via `dep_ids`

### Test with code generation:
```
Add Business-Use tracking to this checkout function:

def process_order(order_id, items):
    order = create_order(items)
    payment = process_payment(order)
    return order
```

Expected response should:
- Add `ensure()` calls in appropriate places
- Use service-layer integration
- Include validators for business rules
- Set up proper dependencies

---

## Troubleshooting

### LLM doesn't seem to know about Business-Use

**Possible causes**:
1. Configuration file not in correct location
2. File not committed to git (for team tools)
3. Tool not restarted after adding config

**Solutions**:
- Verify file path matches tool requirements
- Restart your IDE/tool
- Explicitly reference the file: `@llm_rules/sdk-usage.md`

### LLM suggests incorrect usage

**Check**:
1. Are you using the latest version of the guide?
2. Is the tool reading multiple conflicting configs?
3. Is the example code in your repo up-to-date?

**Solutions**:
- Update `llm_rules/` from the latest Business-Use repo
- Remove outdated `.cursorrules` or instructions
- Add correct examples to your codebase

### Tool-specific issues

- **Cursor**: Try both `.cursorrules` (legacy) and `.cursor/rules/` (new)
- **Copilot**: Check References section to verify instructions are loaded
- **Aider**: Use `--verbose` to see what files are being read
- **Claude Code**: Commands are loaded at startup; restart if needed

---

## Contributing

Found a better way to integrate with a specific tool? Please contribute:

1. Fork the repository
2. Update this README with your findings
3. Add example configurations
4. Submit a pull request

---

## Additional Resources

- [Business-Use Documentation](../README.md)
- [SDK Usage Guide](./sdk-usage.md)
- [Example Projects](../examples/)
- [CLAUDE.md](../CLAUDE.md) - For development with Claude Code

---

## Support

Questions or issues?
- GitHub Issues: https://github.com/desplega-ai/business-use/issues
- Documentation: https://github.com/desplega-ai/business-use#readme
