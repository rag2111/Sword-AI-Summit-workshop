"""Knowledge-base payload contracts for GA and explicitly selected preview APIs."""

import importlib.util
from unittest.mock import Mock

import httpx
import pytest

from _helpers import INFRA

spec = importlib.util.spec_from_file_location("seed_knowledge", INFRA / "scripts" / "seed_knowledge.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)

GA_FIELDS = {"name", "description", "knowledgeSources", "models"}
PREVIEW_FIELDS = {"outputMode", "retrievalInstructions", "retrievalReasoningEffort"}


@pytest.fixture
def search(monkeypatch):
    for name, value in {
        "FOUNDRY_OPENAI_ENDPOINT": "https://example.openai.azure.com",
        "EMBEDDING_DEPLOYMENT": "embedding",
        "EMBEDDING_MODEL": "text-embedding-3-large",
        "CHAT_DEPLOYMENT": "chat",
        "CHAT_MODEL": "gpt-6-luna",
    }.items():
        monkeypatch.setenv(name, value)
    client = Mock(spec=seed.Search)
    client.get.side_effect = [None, {
        "lastSynchronizationState": {"endTime": "2026-09-28T12:00:00Z", "status": "success"}
    }]
    client.upsert.return_value = "created"
    return client


def http_error(status):
    response = httpx.Response(status, request=httpx.Request("PUT", "https://example.search.windows.net"))
    return httpx.HTTPStatusError("Knowledge base request failed", request=response.request, response=response)


@pytest.mark.parametrize("api", ["2026-04-01", "2026-08-01-preview"])
def test_kb_payload_matches_selected_api(search, monkeypatch, api):
    monkeypatch.setattr(seed, "SEARCH_KB_API", api)
    seed.ensure_knowledge_base(search, "/subscriptions/test/storage", "care-docs")
    path, body, version = search.upsert.call_args_list[1].args
    assert path == "knowledgebases/care-kb"
    assert version == api
    assert body["knowledgeSources"] == [{"name": "care-docs-ks"}]
    assert body["models"][0]["azureOpenAIParameters"]["deploymentId"] == "chat"
    if api.endswith("-preview"):
        assert set(body) == GA_FIELDS | PREVIEW_FIELDS
        assert body["outputMode"] == "extractiveData"
        assert body["retrievalReasoningEffort"] == {"kind": "low"}
    else:
        assert set(body) == GA_FIELDS


@pytest.mark.parametrize("api", ["2026-04-01", "2026-08-01-preview"])
def test_no_model_retry_persists_minimal_retrieval_using_preview(search, monkeypatch, api):
    monkeypatch.setattr(seed, "SEARCH_KB_API", api)
    search.upsert.side_effect = ["created", http_error(400), "created"]
    seed.ensure_knowledge_base(search, "/subscriptions/test/storage", "care-docs")
    assert search.upsert.call_count == 3
    path, body, version = search.upsert.call_args.args
    assert path == "knowledgebases/care-kb"
    assert version == (api if api.endswith("-preview") else seed.SEARCH_KB_MCP_API)
    assert "models" not in body and "retrievalInstructions" not in body
    assert body["retrievalReasoningEffort"] == {"kind": "minimal"}
    assert body["outputMode"] == "extractiveData"


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_non_schema_errors_propagate_without_no_model_retry(search, monkeypatch, status):
    monkeypatch.setattr(seed, "SEARCH_KB_API", "2026-04-01")
    error = http_error(status)
    search.upsert.side_effect = ["created", error]
    with pytest.raises(httpx.HTTPStatusError) as caught:
        seed.ensure_knowledge_base(search, "/subscriptions/test/storage", "care-docs")
    assert caught.value is error
    assert search.upsert.call_count == 2


def test_failed_no_model_retry_propagates(search, monkeypatch):
    monkeypatch.setattr(seed, "SEARCH_KB_API", "2026-04-01")
    error = http_error(400)
    search.upsert.side_effect = ["created", http_error(400), error]
    with pytest.raises(httpx.HTTPStatusError) as caught:
        seed.ensure_knowledge_base(search, "/subscriptions/test/storage", "care-docs")
    assert caught.value is error


@pytest.mark.parametrize("mode", ["auto", "kb"])
@pytest.mark.parametrize("failed", [False, True])
def test_main_records_kb_success_and_preserves_fallback_modes(search, monkeypatch, tmp_path, mode, failed):
    monkeypatch.setenv("KNOWLEDGE_MODE", mode)
    monkeypatch.setenv("STORAGE_BLOB_ENDPOINT", "https://example.blob.core.windows.net")
    monkeypatch.setenv("STORAGE_ACCOUNT_ID", "/subscriptions/test/storage")
    monkeypatch.setenv("SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.setattr(seed, "INFRA_DIR", tmp_path)
    monkeypatch.setattr(seed, "OUT_FILE", tmp_path / "out" / "knowledge.json")
    monkeypatch.setattr(seed, "DefaultAzureCredential", Mock())
    monkeypatch.setattr(seed, "Search", Mock(return_value=search))
    monkeypatch.setattr(seed, "upload_docs", Mock(return_value=["test.md"]))
    monkeypatch.setattr(seed, "ensure_fallback_index", Mock())
    monkeypatch.setattr(seed, "ensure_knowledge_base", Mock(side_effect=http_error(400) if failed else None))
    if mode == "kb" and failed:
        with pytest.raises(httpx.HTTPStatusError):
            seed.main()
        assert not seed.OUT_FILE.exists()
    else:
        seed.main()
        assert seed.json.loads(seed.OUT_FILE.read_text())["mode"] == ("index" if failed else "kb")
