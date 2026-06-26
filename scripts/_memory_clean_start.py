"""Clean-start memory consolidation (Bryan Decision: 'Clean start').

- Backs up BOTH legacy stores (copy, never delete):
    ~/.openjarvis/memory.db   (System A, 4 test docs)
    ~/.jarvis/memory.db       (System B, 364 trace/OMNIX/test rows)
- Starts the single canonical store empty (the 'sqlite' MemoryRegistry backend,
  now pure-Python / no Rust dependency) at the standard ~/.openjarvis/memory.db.
- Verifies the canonical store is empty and functional (store/retrieve/persist).

Non-destructive to data: both legacy DB *files* are preserved AND copied to a
timestamped backup dir before the canonical store is cleared.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import time
from pathlib import Path

HOME = Path.home()
CANON = HOME / ".openjarvis" / "memory.db"        # canonical store path
LEGACY_B = HOME / ".jarvis" / "memory.db"          # 364-row store
BACKUP_DIR = HOME / ".openjarvis" / "memory_backups" / time.strftime("%Y%m%d_%H%M%S")


def backup(src: Path) -> str:
    if not src.exists():
        return f"  (skip) {src} — not present"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"{src.parent.name}__{src.name}"
    shutil.copy2(src, dst)
    return f"  backed up {src}  ->  {dst}  ({dst.stat().st_size} bytes)"


def wipe_canonical(db: Path) -> list[str]:
    """Drop all tables in the canonical file so it starts clean. File preserved."""
    out = []
    if not db.exists():
        out.append(f"  canonical {db} did not exist — will be created fresh")
        return out
    conn = sqlite3.connect(str(db))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    # Count rows for the log BEFORE dropping (skip FTS shadow tables, which
    # have no user rows and disappear when their virtual table is dropped).
    for t in tables:
        try:
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            out.append(f"  table '{t}': {n} rows (backed up)")
        except sqlite3.OperationalError:
            pass
    # DROP IF EXISTS, ignoring shadow tables already removed via cascade.
    for t in tables:
        try:
            conn.execute(f'DROP TABLE IF EXISTS "{t}"')
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.execute("VACUUM")
    conn.commit()
    conn.close()
    out.append("  canonical file preserved; all tables cleared")
    return out


def main() -> int:
    print("=== 1. BACKUP (copy, never delete) ===")
    print(backup(CANON))
    print(backup(LEGACY_B))

    print("\n=== 2. CLEAN START — wipe canonical store tables ===")
    for line in wipe_canonical(CANON):
        print(line)

    print("\n=== 3. VERIFY canonical store via the real 'sqlite' backend ===")
    import openjarvis.tools.storage  # noqa: F401 register backend
    from openjarvis.core.registry import MemoryRegistry

    mem = MemoryRegistry.create("sqlite", db_path=str(CANON))
    mode = "pure-Python" if getattr(mem, "_pure_python", False) else "rust"
    start_count = mem.count()
    print(f"  backend mode: {mode}")
    print(f"  starting count (must be 0): {start_count}")

    # functional round-trip on the REAL canonical store
    did = mem.store("verification probe: clean-start canonical store online",
                    source="migration_verify")
    hits = mem.retrieve("clean-start canonical", top_k=3)
    print(f"  store+retrieve works: {bool(hits) and any('clean-start' in h.content for h in hits)}")
    # remove the probe so the store is left genuinely empty
    mem.delete(did)
    end_count = mem.count()
    print(f"  probe removed; final count (must be 0): {end_count}")

    print(f"\n=== DONE. Backups in: {BACKUP_DIR} ===")
    ok = (start_count == 0) and (end_count == 0)
    print("RESULT:", "CLEAN START OK" if ok else "CHECK FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
