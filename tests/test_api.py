from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_version():
    body = client.get("/version").json()
    assert "app_version" in body and "prompt_version" in body


def test_chat_returns_sources():
    body = client.post("/chat", json={"question": "반품 기간이 어떻게 되나요?"}).json()
    assert body["answer"]
    assert "refund.md" in body["sources"]
    assert "search_docs" in body["tool_calls"]


def test_chat_uses_today_tool():
    body = client.post("/chat", json={"question": "오늘 날짜 알려줘"}).json()
    assert "get_today" in body["tool_calls"]


def test_metrics_exposed():
    client.post("/chat", json={"question": "배송비 얼마예요?"})
    text = client.get("/metrics").text
    assert "rag_requests_total" in text
    assert "rag_retrieval_top_score" in text
    assert "rag_app_info" in text
