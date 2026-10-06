# Use Paper Fact Check over MCP

The Model Context Protocol (MCP) lets an AI app call local tools. Paper Fact Check ships a stdio MCP
server with two tools: `check_paper` and `render_report`.

## Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "paperfactcheck": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Biajin-PKU/paperfactcheck", "paperfactcheck", "mcp"]
    }
  }
}
```

Without `uv`, clone the repository and point at the launcher instead:

```json
{
  "mcpServers": {
    "paperfactcheck": {
      "command": "python3",
      "args": ["/path/to/paperfactcheck/skills/paperfactcheck/run.py", "mcp"]
    }
  }
}
```

## Cursor, Windsurf, Cline and other clients

Use the same `command` and `args` in the client's MCP settings.

## Claude Code

```bash
claude mcp add paperfactcheck -- uvx --from git+https://github.com/Biajin-PKU/paperfactcheck paperfactcheck mcp
```

## Tools

| Tool | Arguments | Result |
|---|---|---|
| `check_paper` | `path` (required), `code`, `out_dir`, `offline`, `lang` | Summary of findings; writes `findings.json`, `manuscript.txt`, `report.html` |
| `render_report` | `out_dir` | Rebuilds the report, merging `review.json` |

For the full review (reading the paper, reporting guidelines, reference support), give the model the
instructions in [`skills/paperfactcheck/SKILL.md`](../skills/paperfactcheck/SKILL.md).
