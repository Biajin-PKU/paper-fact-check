"""A Model Context Protocol server over stdio, standard library only.

Tools: `check_paper` runs every check and writes the report; `render_report` rebuilds it after a
review.json is added. Configure a client with: command `paper-fact-check`, args `["mcp"]`
(or `python3 /path/to/skills/paper-fact-check/run.py mcp`).
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from . import __version__

TOOLS = [
    {"name": "check_paper",
     "description": "Fact-check a research paper (PDF, .docx, LaTeX file/folder/zip, Markdown or text) against "
                    "its own evidence: recomputed statistics and percentages, text against tables, reference "
                    "lookups (existence, retraction), figures, declarations and AI-writing residue. Writes "
                    "findings.json, manuscript.txt and report.html to out_dir and returns a summary.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "absolute path to the manuscript"},
         "code": {"type": "string", "description": "optional folder with the released code or data"},
         "out_dir": {"type": "string", "description": "report folder (default: beside the manuscript)"},
         "offline": {"type": "boolean", "description": "skip reference lookups"},
         "lang": {"type": "string", "enum": ["auto", "en", "zh"]}},
         "required": ["path"]}},
    {"name": "render_report",
     "description": "Rebuild report.html and report.md in out_dir, merging review.json (dismissals, edits, "
                    "reviewer findings, guideline items) if present.",
     "inputSchema": {"type": "object", "properties": {"out_dir": {"type": "string"}}, "required": ["out_dir"]}},
]


def _call(name: str, args: dict[str, Any]) -> str:
    from .cli import main
    if name == "check_paper":
        paper = Path(args["path"]).expanduser()
        out = args.get("out_dir") or str(paper.parent / f"paper-fact-check-{paper.stem}")
        argv = ["check", str(paper), "--out", out, "--lang", args.get("lang", "auto")]
        if args.get("code"):
            argv += ["--code", args["code"]]
        if args.get("offline"):
            argv.append("--offline")
    elif name == "render_report":
        argv = ["render", args["out_dir"]]
    else:
        raise ValueError(f"unknown tool {name}")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    if code == 3:
        raise ValueError(buf.getvalue() or "the file could not be read")
    return buf.getvalue()


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification
        return None
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        result: Any = {"protocolVersion": version, "capabilities": {"tools": {}},
                       "serverInfo": {"name": "paper-fact-check", "version": __version__}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        try:
            result = {"content": [{"type": "text", "text": _call(params.get("name", ""), params.get("arguments") or {})}]}
        except Exception as e:  # noqa: BLE001 - reported to the client as a tool error
            result = {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line))
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0
