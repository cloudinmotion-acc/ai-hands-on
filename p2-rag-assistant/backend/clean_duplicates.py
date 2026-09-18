"""
One-off repair for chunks stored before ingest.py deduplicated on re-upload.

Two defects put bad rows in the vector store:
  1. add_documents() appended on every upload, so re-ingesting a file stored a
     second full copy of its chunks.
  2. PDF and Excel loaders recorded the temp upload path as `source`
     (tmpab12cd.pdf), so each re-upload also looked like a different document.

Both are fixed in ingest.py. This script removes the rows they already wrote.

    python clean_duplicates.py            # report only, changes nothing
    python clean_duplicates.py --apply    # perform the deletion

After --apply, re-upload your documents through the UI to restore them with
correct source names.
"""

import re
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from db import get_postgres_url

load_dotenv()

# Matches the mkstemp names main.py generates, with or without a directory.
TEMP_SOURCE = re.compile(r"(^|[\\/])tmp[a-z0-9_]{8}\.(pdf|xlsx|xls|txt)$", re.IGNORECASE)


def main() -> None:
    apply_changes = "--apply" in sys.argv
    engine = create_engine(get_postgres_url())

    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM langchain_pg_embedding")).scalar() or 0
        distinct = conn.execute(
            text("SELECT count(DISTINCT document) FROM langchain_pg_embedding")
        ).scalar() or 0
        sources = conn.execute(text("""
            SELECT cmetadata->>'source' AS source, count(*) AS rows
            FROM langchain_pg_embedding
            GROUP BY 1
            ORDER BY 2 DESC
        """)).fetchall()

    print(f"total rows     : {total}")
    print(f"distinct texts : {distinct}")
    if distinct:
        print(f"duplication    : {total / distinct:.2f}x")

    temp_sources = [s for s, _ in ((r[0] or "", r[1]) for r in sources) if TEMP_SOURCE.search(s)]
    temp_rows = sum(r[1] for r in sources if r[0] and TEMP_SOURCE.search(r[0]))

    print(f"\ntemp-named sources: {len(temp_sources)} ({temp_rows} rows)")
    for s in temp_sources:
        print(f"  {s}")

    # Exact-duplicate texts that survive under a proper source name.
    with engine.connect() as conn:
        dupes = conn.execute(text("""
            SELECT count(*) - count(DISTINCT document)
            FROM langchain_pg_embedding
            WHERE cmetadata->>'source' IS NOT NULL
        """)).scalar() or 0
    print(f"\nredundant duplicate rows overall: {dupes}")

    if not apply_changes:
        print("\nReport only — nothing was changed.")
        print("Re-run with --apply to delete temp-named rows and exact duplicates.")
        return

    with engine.begin() as conn:
        removed_temp = conn.execute(text("""
            DELETE FROM langchain_pg_embedding
            WHERE cmetadata->>'source' ~* '(^|[\\\\/])tmp[a-z0-9_]{8}\\.(pdf|xlsx|xls|txt)$'
        """)).rowcount or 0

        # Keep the lowest ctid per identical (source, document) pair.
        removed_dupes = conn.execute(text("""
            DELETE FROM langchain_pg_embedding a
            USING langchain_pg_embedding b
            WHERE a.ctid > b.ctid
              AND a.document = b.document
              AND a.cmetadata->>'source' IS NOT DISTINCT FROM b.cmetadata->>'source'
        """)).rowcount or 0

    with engine.connect() as conn:
        now = conn.execute(text("SELECT count(*) FROM langchain_pg_embedding")).scalar() or 0

    print(f"\ndeleted {removed_temp} temp-named rows")
    print(f"deleted {removed_dupes} duplicate rows")
    print(f"remaining rows: {now}")
    print("\nRe-upload your documents so they are stored with correct source names.")


if __name__ == "__main__":
    main()
