from app.llm_client import build_headers


def test_build_headers_includes_authorization() -> None:
    headers = build_headers("TEST_KEY")
    assert "Authorization" in headers
    assert headers["Authorization"].endswith("TEST_KEY")


