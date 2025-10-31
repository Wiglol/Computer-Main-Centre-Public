import os, sys, json, time, sqlite3, argparse
from pathlib import Path

# Default DB lives outside temp folders so it persists nicely
DEFAULT_DB = Path(r"C:\Users\Wiggo\Desktop\CentreIndex\paths.db")

def norm(p: str) -> str:
    return str(p).replace("\\", "/").strip()

def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

def connect(db_path: Path):
    ensure_parent(db_path)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    con.execute("PRAGMA mmap_size=30000000000;")
    return con

def ensure_schema(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS paths(
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE
        );
    """)
    # Try to create FTS5 (best-effort). If unavailable, we'll fall back to LIKE.
    try:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS paths_fts USING fts5(path, content='');")
        con.execute("CREATE INDEX IF NOT EXISTS idx_paths_path ON paths(path);")
        con.commit()
        return True
    except sqlite3.OperationalError:
        con.execute("CREATE INDEX IF NOT EXISTS idx_paths_path ON paths(path);")
        con.commit()
        return False

def rebuild_index(db: Path, targets: list[str]):
    start = time.time()
    con = connect(db)
    has_fts = ensure_schema(con)
    cur = con.cursor()

    # Clear old data (safe and simple)
    cur.execute("DELETE FROM paths;")
    if has_fts:
        cur.execute("DELETE FROM paths_fts;")
    con.commit()

    total = 0
    def add_batch(batch):
        nonlocal total
        if not batch: return
        cur.executemany("INSERT OR IGNORE INTO paths(path) VALUES (?);", ((p,) for p in batch))
        if has_fts:
            cur.executemany("INSERT INTO paths_fts(path) VALUES (?);", ((p,) for p in batch))
        total += len(batch)

    # Expand targets (drives or folders)
    norm_targets = []
    for t in targets:
        t = t.strip()
        if not t: continue
        # Allow "C" or "C:" or "C:/"
        if len(t) == 1 and t.isalpha():
            base = Path(t + ":/")  # C:/
        else:
            base = Path(t)
            # If "C:" given, make it "C:/"
            if base.drive and str(base) == base.drive:
                base = Path(base.drive + "/")
        norm_targets.append(base)

    print("[INDEX] Starting fresh scan…")
    BATCH = 2000
    for base in norm_targets:
        print(f"[SCAN] {base}")
        try:
            if not base.exists():
                print(f"[WARN] {base} does not exist or is not accessible.")
                continue
            batch = []
            # Use rglob; ignore permission errors by try/except on each iteration
            it = base.rglob("*")
            for p in it:
                try:
                    batch.append(norm(str(p)))
                    if len(batch) >= BATCH:
                        add_batch(batch); con.commit(); batch.clear()
                except Exception:
                    # Skip unreadable entries
                    continue
            if batch:
                add_batch(batch); con.commit(); batch.clear()
        except Exception as e:
            print(f"[WARN] {base}: {e}")

    con.commit()
    dur = time.time() - start
    print(f"[BUILD] Indexed ~{total:,} paths in {dur:.1f}s → {db}")
    con.close()

def count_paths(db: Path) -> int:
    con = connect(db)
    try:
        (n,) = con.execute("SELECT COUNT(*) FROM paths;").fetchone()
        return int(n)
    finally:
        con.close()

def query_paths(db: Path, q: str, limit: int = 50) -> list[tuple[str,int]]:
    """
    Multi-word search:
      - "abc def" => path must contain "abc" AND "def" (case-insensitive)
      - If too few hits, relax to OR (any term) to fill up to limit
    Returns list of (path, score).
    """
    con = connect(db)
    try:
        terms = [t.strip().lower() for t in q.split() if t.strip()]
        if not terms:
            return []

        # AND match (strict)
        and_sql = " AND ".join(["LOWER(path) LIKE ?"] * len(terms))
        and_params = [f"%{t}%" for t in terms]
        rows = con.execute(
            f"SELECT path FROM paths WHERE {and_sql} LIMIT ?;",
            (*and_params, limit)
        ).fetchall()
        out = [(r[0], 100) for r in rows]

        # If not enough, fill with OR match (but don’t duplicate)
        if len(out) < limit and len(terms) > 1:
            or_sql = " OR ".join(["LOWER(path) LIKE ?"] * len(terms))
            or_params = [f"%{t}%" for t in terms]
            rows2 = con.execute(
                f"SELECT path FROM paths WHERE {or_sql} LIMIT ?;",
                (*or_params, limit)
            ).fetchall()
            seen = {p for (p, _) in out}
            for (p,) in rows2:
                if p not in seen:
                    out.append((p, 90))
                    seen.add(p)
                if len(out) >= limit:
                    break

        return out[:limit]
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description="Local Path Index (no server)")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite DB")
    parser.add_argument("--build", help="Comma-separated list of drives/folders (e.g. C,E,F or C:/Users/Wiggo,C,E,F)")
    parser.add_argument("--count", action="store_true", help="Print number of indexed paths")
    parser.add_argument("--query", help="Search term to find paths")
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    db = Path(args.db)

    if args.build:
        targets = [x.strip() for x in args.build.split(",") if x.strip()]
        rebuild_index(db, targets)
        return

    if args.count:
        print(count_paths(db))
        return

    if args.query is not None:
        results = query_paths(db, args.query, args.limit)
        # Print JSON for easy consumption by other tools
        print(json.dumps([{"path": p, "score": s} for (p, s) in results], ensure_ascii=False))
        return

    print("Usage:")
    print("  python path_index_local.py --build C:/Users/Wiggo,C,E,F")
    print("  python path_index_local.py --count")
    print("  python path_index_local.py --query atlauncher --limit 25")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("⚠️ Error:", e)
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")

