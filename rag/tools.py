"""Optional commands for downloading and indexing judgments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from utils.indian_kanoon import IndianKanoonClient
from rag.pipeline import EmbeddingModel, VectorStore, clean_text, create_chunks, load_judgment

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "judgments"


def download(query: str, page: int = 0) -> int:
    """Download Supreme Court judgments from Indian Kanoon based on a query."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = IndianKanoonClient().search(query=query, page=page, court="supremecourt")
    downloaded = 0
    
    for result in results.get("docs", []):
        doc_id = result.get("tid")
        if not doc_id:
            continue
        try:
            document = IndianKanoonClient().get_document(str(doc_id))
            with (DATA_DIR / f"{doc_id}.json").open("w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
            downloaded += 1
            print(f"Downloaded {doc_id}")
        except Exception as exc:
            print(f"Failed {doc_id}: {exc}")
            
    return downloaded


def index_judgments(data_dir: Path = DATA_DIR) -> int:
    """Load JSON judgment files, chunk text, generate embeddings, and add them to the vector store."""
    chunks_all, metadata_all, ids_all = [], [], []
    
    for path in sorted(data_dir.glob("*.json")):
        document = load_judgment(path)
        chunks = create_chunks(clean_text(document.text))
        
        for index, chunk in enumerate(chunks):
            chunks_all.append(chunk)
            metadata_all.append({
                "doc_id": document.doc_id,
                "title": document.title,
                "source": document.source,
                "chunk_id": index,
                **{key: str(value) for key, value in document.metadata.items()},
            })
            ids_all.append(f"{document.doc_id}_{index}")
            
        print(f"{document.title}: {len(chunks)} chunks")
        
    if not chunks_all:
        print("No judgment JSON files found.")
        return 0
        
    VectorStore().add_documents(
        chunks_all,
        EmbeddingModel().encode(chunks_all),
        metadata_all,
        ids_all,
    )
    print(f"Indexed {len(chunks_all)} chunks")
    return len(chunks_all)


def main() -> None:
    """Parse command-line arguments and run either download or index routines."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("--query", default="Article 21")
    download_parser.add_argument("--page", type=int, default=0)
    
    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    
    args = parser.parse_args()
    
    if args.command == "download":
        print(f"Downloaded {download(args.query, args.page)} judgments")
    else:
        index_judgments(args.data_dir)


if __name__ == "__main__":
    main()