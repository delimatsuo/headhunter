#!/usr/bin/env python3
"""
Safe Firestore cleanup utility with dry-run by default.

Usage examples:
  Dry run (default):
    python scripts/cleanup_firestore.py --collections enriched_profiles candidate_embeddings embeddings

  Execute deletion (requires proper credentials):
    python scripts/cleanup_firestore.py --collections enriched_profiles candidate_embeddings embeddings --execute

Notes:
  - You can set GOOGLE_APPLICATION_CREDENTIALS or rely on Application Default Credentials.
  - For unit testing, the core functions accept an injected client with the Firestore-like interface.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Protocol


class _DocRef(Protocol):
    def delete(self) -> None: ...


class _CollectionRef(Protocol):
    def stream(self) -> Iterable[_DocumentSnapshot]: ...


class _DocumentSnapshot(Protocol):
    @property
    def reference(self) -> _DocRef: ...


class _FirestoreLike(Protocol):
    def collection(self, name: str) -> _CollectionRef: ...


def count_documents(db: _FirestoreLike, collection: str) -> int:
    count = 0
    for _ in db.collection(collection).stream():
        count += 1
    return count


def delete_collection(db: _FirestoreLike, collection: str, *, batch_size: int = 250, dry_run: bool = True) -> int:
    """Delete a collection in batches. Returns number of docs targeted.

    If dry_run=True, does not perform deletions, only counts.
    """
    deleted = 0
    batch: List[_DocRef] = []
    for doc in db.collection(collection).stream():
        batch.append(doc.reference)
        if len(batch) >= batch_size:
            if not dry_run:
                for ref in batch:
                    ref.delete()
            deleted += len(batch)
            batch.clear()
    # flush remainder
    if batch:
        if not dry_run:
            for ref in batch:
                ref.delete()
        deleted += len(batch)
    return deleted


def get_firestore_client():
    # Imported lazily to keep tests independent of firebase_admin
    import firebase_admin
    from firebase_admin import firestore

    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
        except Exception:
            # Fallback to application default credentials
            from firebase_admin import credentials

            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
    return firestore.client()


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Safe Firestore cleanup (dry-run by default)")
    parser.add_argument(
        "--collections",
        nargs="+",
        required=True,
        help="Collection names to delete (in batches)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Delete batch size (default: 250)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform deletions (default is dry-run)",
    )
    args = parser.parse_args(argv)

    dry_run = not args.execute
    db = get_firestore_client()

    print(("[DRY-RUN] " if dry_run else "") + "Starting Firestore cleanup...")
    total = 0
    for coll in args.collections:
        pre_count = count_documents(db, coll)
        print(f"Collection '{coll}': {pre_count} documents found")
        if pre_count == 0:
            continue
        deleted = delete_collection(db, coll, batch_size=args.batch_size, dry_run=dry_run)
        total += deleted
        print(("[DRY-RUN] " if dry_run else "") + f"Deleted {deleted} docs from '{coll}'")
    print(("[DRY-RUN] " if dry_run else "") + f"Cleanup complete. Targeted {total} docs across {len(args.collections)} collections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

