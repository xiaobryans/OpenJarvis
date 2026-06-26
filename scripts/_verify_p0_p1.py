"""Live P0+P1 verification harness — real ollama, real agent, temp memory DB.

Runs the ACTUAL HTTP chat route via TestClient against a locally-built app
wired exactly like the server (orchestrator agent + default tools + sqlite
memory), using local qwen3.5:2b so there is zero cloud spend, and a TEMP
memory db so the real ~/.openjarvis/memory.db is never touched.

Prints real PASS/FAIL with the model's actual output. No assumptions.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

MODEL = "qwen3.5:2b"


def build_tools():
    import openjarvis.tools  # noqa: F401  trigger registration
    from openjarvis.core.registry import ToolRegistry
    from openjarvis.tools._stubs import BaseTool

    allowed = {
        "think", "calculator", "web_search", "current_time",
        "file_read", "file_search", "http_request",
    }
    tools = []
    for name in ToolRegistry.keys():
        if name not in allowed:
            continue
        cls = ToolRegistry.get(name)
        if isinstance(cls, type) and issubclass(cls, BaseTool):
            tools.append(cls())
    return tools


def build_memory(db_path: str):
    """Return (backend, label). Prefer the real Rust-backed sqlite store; if the
    native ext isn't built in this venv, fall back to a real on-disk
    pure-Python backend so the save-back/retrieve WIRING is still tested with
    genuine persistence."""
    from openjarvis.core.registry import MemoryRegistry
    import openjarvis.tools.storage  # noqa: F401  register sqlite memory

    try:
        return MemoryRegistry.create("sqlite", db_path=db_path), "rust-sqlite (production)"
    except Exception as exc:  # MemoryBackendUnavailable when rust ext missing
        print(f"# NOTE: production sqlite memory unavailable ({type(exc).__name__}); "
              f"using pure-Python on-disk backend to test wiring.\n")
        return PyMemoryBackend(db_path), "py-sqlite (wiring-test double, real disk)"


def _make_py_backend_cls():
    import sqlite3
    import uuid as _uuid
    from openjarvis.tools.storage._stubs import MemoryBackend, RetrievalResult

    class _PyMem(MemoryBackend):
        backend_id = "py_sqlite_test"

        def __init__(self, db_path):
            self._c = sqlite3.connect(db_path, check_same_thread=False)
            self._c.execute(
                "CREATE TABLE IF NOT EXISTS docs(id TEXT PRIMARY KEY, content TEXT, source TEXT)"
            )
            self._c.commit()

        def store(self, content, *, source="", metadata=None):
            did = _uuid.uuid4().hex
            self._c.execute("INSERT INTO docs VALUES(?,?,?)", (did, content, source))
            self._c.commit()
            return did

        def retrieve(self, query, *, top_k=5, **kwargs):
            words = [w.lower().strip(".,?!") for w in query.split() if len(w) > 2]
            rows = self._c.execute("SELECT content FROM docs").fetchall()
            hits = []
            for (content,) in rows:
                cl = content.lower()
                overlap = sum(1 for w in words if w in cl)
                if overlap:
                    hits.append(RetrievalResult(content=content, score=1.0))
            return hits[:top_k]

        def search(self, query, top_k=5):
            return self.retrieve(query, top_k=top_k)

        def delete(self, doc_id):
            self._c.execute("DELETE FROM docs WHERE id=?", (doc_id,))
            self._c.commit()
            return True

        def clear(self):
            self._c.execute("DELETE FROM docs")
            self._c.commit()

    return _PyMem


def make_app(db_path: str):
    from openjarvis.core.config import load_config
    from openjarvis.engine.ollama import OllamaEngine
    from openjarvis.agents.orchestrator import OrchestratorAgent
    from openjarvis.server.app import create_app

    config = load_config()
    config.memory.db_path = db_path
    config.agent.context_from_memory = True

    engine = OllamaEngine()
    tools = build_tools()
    agent = OrchestratorAgent(engine, MODEL, tools=tools, max_turns=4)
    mem, label = build_memory(db_path)
    print(f"# memory backend: {label}")

    app = create_app(
        engine, MODEL, agent=agent, config=config,
        memory_backend=mem, engine_name="ollama", api_key="",
    )
    return app, agent, mem


PyMemoryBackend = None  # set in main() once package is importable


def stream_chat(client: TestClient, text: str) -> tuple[str, dict]:
    """POST a streaming chat turn; return (assistant_text, finish_telemetry)."""
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": text}],
        "stream": True,
        "max_tokens": 400,
    }
    content = ""
    telemetry = {}
    with client.stream("POST", "/v1/chat/completions", json=body) as r:
        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload.strip() == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            ch = (obj.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            if delta.get("content"):
                content += delta["content"]
            if obj.get("telemetry"):
                telemetry = obj["telemetry"]
    return content, telemetry


def main() -> int:
    global PyMemoryBackend
    PyMemoryBackend = _make_py_backend_cls()

    tmp = tempfile.mkdtemp(prefix="jarvis_verify_")
    db = str(Path(tmp) / "memory.db")
    print(f"# temp memory db: {db}\n")

    app, agent, mem = make_app(db)
    client = TestClient(app)
    results = []

    # --- T1: time question (date injection + routing through agent) ---
    txt, tel = stream_chat(client, "What time is it right now?")
    ok = ("2026" in txt) and ("June" in txt or "Friday" in txt or ":" in txt)
    results.append(("T1 what time is it", ok, txt.strip()[:200], tel))

    # --- T2: day of week ---
    txt, tel = stream_chat(client, "What day of the week is it today?")
    ok = "Friday" in txt
    results.append(("T2 what day is it", ok, txt.strip()[:200], tel))

    # --- T3: tool execution (direct agent, inspect tool_results) ---
    from openjarvis.agents._stubs import AgentContext
    r = agent.run(
        "Use your current_time tool to look up the exact current time, "
        "then tell me.",
        context=AgentContext(),
    )
    tool_names = [getattr(t, "tool_name", "?") for t in (r.tool_results or [])]
    ok = len(tool_names) > 0
    results.append((
        "T3 tool actually executes",
        ok,
        f"tools_executed={tool_names} | answer={r.content.strip()[:120]}",
        {},
    ))

    # --- T4: memory save + retrieve (same session) ---
    stream_chat(client, "Please remember this: my favorite color is teal "
                        "and my dog is named Pixel.")
    rows = mem.search("favorite color teal", top_k=5) if hasattr(mem, "search") else []
    saved = mem.retrieve("favorite color teal", top_k=5)
    saved_texts = [getattr(d, "content", str(d)) for d in saved]
    saved_ok = any("teal" in s.lower() for s in saved_texts)
    txt, tel = stream_chat(client, "What is my favorite color?")
    recall_ok = "teal" in txt.lower()
    results.append((
        "T4a memory SAVED to store", saved_ok,
        f"store hits={len(saved_texts)}: {[s[:50] for s in saved_texts][:3]}", {},
    ))
    results.append((
        "T4b memory RECALLED in chat", recall_ok, txt.strip()[:200], tel,
    ))

    # --- T5: cross-session persistence (new app, same db) ---
    del client, app
    app2, agent2, mem2 = make_app(db)
    client2 = TestClient(app2)
    txt, tel = stream_chat(client2, "What is my dog's name?")
    cross_ok = "pixel" in txt.lower()
    results.append((
        "T5 cross-session memory loads", cross_ok, txt.strip()[:200], tel,
    ))

    # --- report ---
    print("\n================ VERIFICATION RESULTS ================")
    all_ok = True
    for name, ok, detail, tel in results:
        all_ok = all_ok and ok
        flag = "PASS" if ok else "FAIL"
        tel_s = f" | telemetry={tel}" if tel else ""
        print(f"[{flag}] {name}\n        {detail}{tel_s}")
    print("======================================================")
    print("OVERALL:", "ALL PASS" if all_ok else "SOME FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
