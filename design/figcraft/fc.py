"""Cliente mínimo do servidor MCP do FigCraft (figcraft-cli mcp, headless, stdio).

Uso:
    from fc import FC
    fc = FC()                       # inicia o servidor
    r = fc.cmd("node.create", {...})  # qualquer comando do registro
    fc.set([id], {...})             # node.set
    fc.get(id, depth=2)             # get_node
    fc.save("arquivo.figcraft")
    fc.png("saida.png", ids=[id], scale=1)
"""
import base64
import json
import os
import subprocess

CLI = os.environ.get(
    "FIGCRAFT_CLI", "figcraft-cli"
)


class FCError(RuntimeError):
    pass


class FC:
    def __init__(self, cli=CLI, extra_args=None):
        args = [cli, "mcp"] + (extra_args or [])
        self.p = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._id = 0
        self._rpc("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "prumo-builder", "version": "1"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # --- transporte -------------------------------------------------------
    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def _rpc(self, method, params):
        self._id += 1
        mid = self._id
        self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                err = self.p.stderr.read()
                raise FCError(f"servidor encerrou: {err[-2000:]}")
            msg = json.loads(line)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise FCError(json.dumps(msg["error"], ensure_ascii=False))
                return msg["result"]

    def tool(self, name, args):
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        if res.get("isError"):
            txt = " ".join(c.get("text", "") for c in res.get("content", []))
            raise FCError(f"{name} {json.dumps(args, ensure_ascii=False)[:600]} -> {txt}")
        return res

    @staticmethod
    def _json(res):
        if "structuredContent" in res:
            return res["structuredContent"]
        for c in res.get("content", []):
            if c.get("type") == "text":
                try:
                    return json.loads(c["text"])
                except json.JSONDecodeError:
                    return c["text"]
        return res

    # --- atalhos ------------------------------------------------------------
    def cmd(self, command, params=None):
        return self._json(self.tool("run_command", {"command": command, "params": params or {}}))

    def batch(self, commands, label=None):
        args = {"commands": commands}
        if label:
            args["label"] = label
        return self._json(self.tool("batch", args))

    def create(self, type_, **kw):
        args = {"type": type_}
        args.update({k: v for k, v in kw.items() if v is not None})
        r = self._json(self.tool("create_node", args))
        return r["id"] if isinstance(r, dict) and "id" in r else r

    def set(self, ids, props):
        if not isinstance(ids, list):
            ids = [ids]
        return self._json(self.tool("set_properties", {"ids": ids, "props": props}))

    def get(self, id_, depth=1):
        return self._json(self.tool("get_node", {"id": id_, "depth": depth}))

    def inspect(self, depth=2, all_pages=False):
        return self._json(self.tool("inspect_document", {"depth": depth, "allPages": all_pages}))

    def open(self, path):
        return self._json(self.tool("open_file", {"path": path}))

    def save(self, path):
        return self._json(self.tool("save_file", {"path": path}))

    def png(self, path, ids=None, scale=1.0, max_size=None):
        args = {"format": "png", "path": path, "scale": scale}
        if ids:
            args["ids"] = ids
        return self._json(self.tool("export", args))

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()
