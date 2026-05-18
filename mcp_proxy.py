#!/usr/bin/env python3
"""
MCP Schema Proxy for PatSnap Pharma Intelligence
─────────────────────────────────────────────────
PatSnap's MCP server uses anyOf/oneOf/allOf at the TOP level of inputSchema
for tools that accept multiple optional filter params (meaning "at least one
required"). The Claude API rejects any request whose tool list contains such
schemas. This proxy transparently strips those top-level combiners before
handing tool definitions to Claude Code.

Usage:
  python3.10 mcp_proxy.py          # starts on 127.0.0.1:3099

Then configure Claude Code to use this proxy instead of PatSnap directly:
  claude mcp remove pharma_intelligence
  claude mcp add --transport http pharma_intelligence http://127.0.0.1:3099/mcp
"""

import json
import asyncio
import urllib.request
import urllib.parse
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

UPSTREAM_URL = "https://connect.zhihuiya.com/096456/logic-mcp"
API_KEY = "sk-3F0NsY7KOt2ZyO72XkgwUIwD80xSfBjCNKp7juA92d0HWpKu"
PROXY_PORT = 3099

# SSL context that skips verification for corporate proxy environments
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def _upstream_url() -> str:
    return f"{UPSTREAM_URL}?apikey={API_KEY}"


def _resolve_combiner(prop: dict) -> dict:
    """Collapse anyOf/oneOf/allOf [real_type, null] → real_type recursively."""
    if not isinstance(prop, dict):
        return prop
    result = {}
    for combiner in ("anyOf", "oneOf", "allOf"):
        if combiner in prop:
            options = prop[combiner]
            non_null = [o for o in options
                        if not (isinstance(o, dict) and o.get("type") == "null")]
            if len(non_null) == 1:
                # Merge the single non-null option's fields into result
                for k, v in non_null[0].items():
                    result[k] = _resolve_combiner(v) if isinstance(v, dict) else v
            elif len(non_null) > 1:
                # Keep the combiner but strip null variants
                result[combiner] = [_resolve_combiner(o) for o in non_null]
            break  # Only handle the first combiner found
    for k, v in prop.items():
        if k in ("anyOf", "oneOf", "allOf"):
            continue
        if k == "properties" and isinstance(v, dict):
            result[k] = {pk: _resolve_combiner(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            result[k] = _resolve_combiner(v)
        else:
            result[k] = v
    return result


def fix_input_schema(schema: dict) -> dict:
    """Strip top-level anyOf/oneOf/allOf and recursively resolve nested ones."""
    # Strip top-level combiners first
    cleaned = {k: v for k, v in schema.items() if k not in ("anyOf", "allOf", "oneOf")}
    # Recursively fix properties
    if "properties" in cleaned and isinstance(cleaned["properties"], dict):
        cleaned["properties"] = {
            k: _resolve_combiner(v)
            for k, v in cleaned["properties"].items()
        }
    return cleaned


def fix_tools_list_response(data: dict) -> dict:
    result = data.get("result", {})
    tools = result.get("tools")
    if not tools:
        return data
    fixed_tools = []
    for tool in tools:
        if "inputSchema" in tool:
            tool = {**tool, "inputSchema": fix_input_schema(tool["inputSchema"])}
        fixed_tools.append(tool)
    return {**data, "result": {**result, "tools": fixed_tools}}


def call_upstream(body: dict) -> str:
    """POST to upstream, return raw response body (SSE text)."""
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        _upstream_url(),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=60) as resp:
        return resp.read().decode()


def transform_response(raw: str, method: str) -> str:
    """If this is a tools/list response, rewrite tool schemas."""
    if method != "tools/list":
        return raw
    lines = raw.splitlines(keepends=True)
    out = []
    for line in lines:
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:].strip())
                data = fix_tools_list_response(data)
                out.append(f"data: {json.dumps(data)}\n")
                continue
            except json.JSONDecodeError:
                pass
        out.append(line)
    return "".join(out)


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[proxy] {fmt % args}")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(length)
        try:
            body = json.loads(body_bytes)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        method = body.get("method", "")
        try:
            raw = call_upstream(body)
            transformed = transform_response(raw, method)
        except Exception as e:
            error = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32603, "message": str(e)},
            }
            out = f"event: message\ndata: {json.dumps(error)}\n\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(out)
            return

        out = transformed.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(out)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    print(f"PatSnap MCP proxy running on http://127.0.0.1:{PROXY_PORT}/mcp")
    print("Configure Claude Code:")
    print("  claude mcp remove pharma_intelligence")
    print(f"  claude mcp add --transport http pharma_intelligence http://127.0.0.1:{PROXY_PORT}/mcp")
    print("Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
