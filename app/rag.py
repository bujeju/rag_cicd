"""아주 단순한 RAG 검색기.

1) data/docs/*.md 를 문단 단위로 자른다 (chunking)
2) TF-IDF(글자 n-gram)로 벡터화한다  → 한국어도 형태소 분석기 없이 동작
3) 질문과 코사인 유사도가 높은 chunk 를 TOP_K 개 돌려준다

※ 심화 과제: TF-IDF 대신 임베딩 API + 벡터DB(Chroma 등)로 교체해 보기
"""
import pickle
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app import config


@dataclass
class Chunk:
    source: str   # 파일명 (예: refund.md)
    text: str


def split_into_chunks(text: str, source: str, max_chars: int = 200) -> list[Chunk]:
    """빈 줄 기준으로 문단을 나누고, 너무 짧은 문단은 이어 붙인다."""
    chunks, buf = [], ""
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        if len(buf) + len(para) > max_chars and buf:
            chunks.append(Chunk(source, buf.strip()))
            buf = ""
        buf += para + "\n"
    if buf.strip():
        chunks.append(Chunk(source, buf.strip()))
    return chunks


def build_index(docs_dir: Path = config.DOCS_DIR, index_path: Path = config.INDEX_PATH) -> int:
    chunks: list[Chunk] = []
    for f in sorted(docs_dir.glob("*.md")):
        chunks += split_into_chunks(f.read_text(encoding="utf-8"), f.name)
    if not chunks:
        raise RuntimeError(f"문서가 없습니다: {docs_dir}")

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3))
    matrix = vectorizer.fit_transform([c.text for c in chunks])

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "wb") as fp:
        pickle.dump({"chunks": chunks, "vectorizer": vectorizer, "matrix": matrix}, fp)
    return len(chunks)


class Retriever:
    def __init__(self, index_path: Path = config.INDEX_PATH):
        if not index_path.exists():
            build_index(index_path=index_path)
        with open(index_path, "rb") as fp:
            data = pickle.load(fp)
        self.chunks: list[Chunk] = data["chunks"]
        self.vectorizer = data["vectorizer"]
        self.matrix = data["matrix"]

    def search(self, query: str, top_k: int = config.TOP_K) -> list[dict]:
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        best = scores.argsort()[::-1][:top_k]
        return [
            {"source": self.chunks[i].source, "text": self.chunks[i].text, "score": round(float(scores[i]), 3)}
            for i in best
        ]
