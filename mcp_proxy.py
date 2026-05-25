#!/usr/bin/env python3
"""
MCP Schema Proxy for PatSnap (all services)
─────────────────────────────────────────────────
PatSnap MCP servers use anyOf/oneOf/allOf in inputSchema properties, which
the Claude API rejects (400 error). This proxy transparently strips those
combiners before handing tool definitions to Claude Code.

Usage:
  # pharma_intelligence (port 3099, default)
  python3.10 mcp_proxy.py

  # biology_modality (port 3100)
  python3.10 mcp_proxy.py --port 3100 --upstream https://connect.zhihuiya.com/06e741/logic-mcp

  # chemical_molecular (port 3101)
  python3.10 mcp_proxy.py --port 3101 --upstream https://connect.zhihuiya.com/713886/logic-mcp

MCP configuration:
  claude mcp remove <service> && claude mcp add --transport http <service> http://127.0.0.1:<port>/mcp
"""

import json
import os
import argparse
import urllib.request
import ssl
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler


def _load_api_key() -> str:
    """Return API key from PATSNAP_API_KEY env var, .env file, or fallback."""
    env_key = os.environ.get("PATSNAP_API_KEY")
    if env_key:
        return env_key
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("PATSNAP_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


APIKEY = _load_api_key()

DEFAULTS = {
    "upstream": "https://connect.zhihuiya.com/096456/logic-mcp",
    "port": 3099,
}

# Filled at startup from CLI args
UPSTREAM_URL: str = ""
PROXY_PORT: int = 0

# SSL context that skips verification for corporate proxy environments
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def _upstream_url() -> str:
    return f"{UPSTREAM_URL}?apikey={APIKEY}"


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
                    if k == "properties" and isinstance(v, dict):
                        result[k] = {pk: _resolve_combiner(pv) for pk, pv in v.items()}
                    elif k == "items" and isinstance(v, dict):
                        result[k] = _resolve_combiner(v)
                    else:
                        result[k] = _resolve_combiner(v) if isinstance(v, dict) else v
            elif len(non_null) > 1:
                # If all options are simple {type: X} schemas, pick the first (API rejects anyOf)
                all_simple = all(
                    isinstance(o, dict) and set(o.keys()) <= {"type", "title"}
                    for o in non_null
                )
                if all_simple:
                    for k, v in non_null[0].items():
                        result[k] = v
                else:
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
    parser = argparse.ArgumentParser(description="PatSnap MCP schema-fix proxy")
    parser.add_argument("--port", type=int, default=DEFAULTS["port"],
                        help=f"Local proxy port (default: {DEFAULTS['port']})")
    parser.add_argument("--upstream", default=DEFAULTS["upstream"],
                        help="Upstream PatSnap MCP URL (without apikey)")
    args = parser.parse_args()

    UPSTREAM_URL = args.upstream
    PROXY_PORT = args.port

    server = HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    print(f"PatSnap MCP proxy  →  http://127.0.0.1:{PROXY_PORT}/mcp")
    print(f"Upstream: {UPSTREAM_URL}")
    print("Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
