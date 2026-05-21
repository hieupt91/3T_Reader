"""Semantic search — tìm kiếm theo nghĩa trong tài liệu PDF.

Dùng embeddings từ API (OpenAI hoặc Anthropic) và cosine similarity.
Không cần FAISS — dùng numpy thuần để tránh phụ thuộc nặng.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class SearchChunk:
    page: int
    text: str
    score: float = 0.0


@dataclass
class SearchIndex:
    """Index embedding cho một file PDF."""
    pdf_path: str
    chunks: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    embeddings: Optional[np.ndarray] = None   # shape (N, D)

    @property
    def is_built(self) -> bool:
        return self.embeddings is not None and len(self.chunks) > 0


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """Cắt văn bản thành các đoạn nhỏ có chồng lấp."""
    words = text.split()
    if not words:
        return []
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
        i += chunk_size - overlap
    return chunks


def _get_embeddings(texts: list[str]) -> Optional[np.ndarray]:
    """Lấy embeddings từ OpenAI. Trả về None nếu không có API key."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        vecs = [item.embedding for item in resp.data]
        return np.array(vecs, dtype=np.float32)
    except Exception:
        return None


def _cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Tính cosine similarity giữa query và tất cả vectors."""
    q = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    normalized = matrix / norms
    return normalized @ q


def build_index(pdf_path: str, progress_cb=None) -> tuple[SearchIndex, str]:
    """
    Xây dựng search index cho một file PDF.
    Returns (index, error_message). error_message rỗng nếu thành công.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return SearchIndex(pdf_path=pdf_path), "Semantic search cần OPENAI_API_KEY."

    try:
        import fitz
        doc = fitz.open(pdf_path)
        all_chunks = []
        all_pages = []
        try:
            for i, page in enumerate(doc):
                text = page.get_text("text").strip()
                if not text:
                    continue
                chunks = _chunk_text(text)
                all_chunks.extend(chunks)
                all_pages.extend([i + 1] * len(chunks))
                if progress_cb:
                    progress_cb(f"Đang phân tích trang {i+1}/{doc.page_count}…")
        finally:
            doc.close()
    except Exception as e:
        return SearchIndex(pdf_path=pdf_path), f"Không đọc được PDF: {e}"

    if not all_chunks:
        return SearchIndex(pdf_path=pdf_path), "Tài liệu không có văn bản."

    if progress_cb:
        progress_cb(f"Đang tạo embeddings cho {len(all_chunks)} đoạn văn…")

    # Gửi theo batch 100 chunks
    all_vecs = []
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        vecs = _get_embeddings(batch)
        if vecs is None:
            return SearchIndex(pdf_path=pdf_path), "Không lấy được embeddings từ OpenAI."
        all_vecs.append(vecs)

    embeddings = np.vstack(all_vecs)
    index = SearchIndex(
        pdf_path=pdf_path,
        chunks=all_chunks,
        pages=all_pages,
        embeddings=embeddings,
    )
    return index, ""


def search(index: SearchIndex, query: str, top_k: int = 5) -> tuple[list[SearchChunk], str]:
    """
    Tìm kiếm theo nghĩa trong index.
    Returns (results, error_message).
    """
    if not index.is_built:
        return [], "Index chưa được xây dựng."
    if not query.strip():
        return [], "Câu hỏi rỗng."

    query_vec = _get_embeddings([query])
    if query_vec is None:
        return [], "Không lấy được embedding cho câu hỏi."

    scores = _cosine_similarity(query_vec[0], index.embeddings)
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] > 0.3:  # Ngưỡng tối thiểu
            results.append(SearchChunk(
                page=index.pages[idx],
                text=index.chunks[idx],
                score=float(scores[idx]),
            ))

    if not results:
        return [], "Không tìm thấy đoạn văn liên quan."

    return results, ""


def save_index(index: SearchIndex, cache_dir: str) -> None:
    """Lưu index vào disk để tái sử dụng."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    name = Path(index.pdf_path).stem
    base = os.path.join(cache_dir, name)
    meta = {"pdf_path": index.pdf_path, "chunks": index.chunks, "pages": index.pages}
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    np.save(base + ".npy", index.embeddings)


def load_index(pdf_path: str, cache_dir: str) -> Optional[SearchIndex]:
    """Tải index từ disk nếu còn mới hơn file PDF."""
    name = Path(pdf_path).stem
    base = os.path.join(cache_dir, name)
    json_path, npy_path = base + ".json", base + ".npy"
    if not (os.path.exists(json_path) and os.path.exists(npy_path)):
        return None
    # Kiểm tra cache còn mới không
    if os.path.getmtime(pdf_path) > os.path.getmtime(json_path):
        return None
    try:
        with open(json_path, encoding="utf-8") as f:
            meta = json.load(f)
        embeddings = np.load(npy_path)
        return SearchIndex(
            pdf_path=pdf_path,
            chunks=meta["chunks"],
            pages=meta["pages"],
            embeddings=embeddings,
        )
    except Exception:
        return None
