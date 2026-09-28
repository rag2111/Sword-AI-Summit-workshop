# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "azure-identity==1.25.3",
#   "azure-storage-blob==12.30.3",
#   "httpx==0.28.1",
# ]
# ///
"""Seed the knowledge layer (idempotent). Run by Terraform (terraform_data + local-exec) or by hand:

    uv run scripts/seed_knowledge.py            # all settings come from environment variables

Steps
  1. Upload infra/data/care-docs/*.md to the `care-docs` blob container (skips unchanged files by MD5).
  2. Create the FALLBACK classic index `care-docs` + data source + indexer (GA Search REST API).
     Always created: cheap, and it lets the base agent switch to the Azure AI Search tool instantly.
  3. PREVIEW/GA mix: create the Foundry IQ knowledge source `care-docs-ks` (kind azureBlob) and the
     knowledge base `care-kb` (agentic retrieval). If that API is unavailable and KNOWLEDGE_MODE=auto,
     fall back to mode "index".
  4. Write infra/out/knowledge.json, consumed by create_base_agent.py.

Identity: your Azure CLI login (Terraform grants you Storage Blob Data Contributor, Search Service
Contributor and Search Index Data Contributor). This is an admin path and does NOT go through APIM
(see docs/apim-exceptions/infra.md).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

INFRA_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = INFRA_DIR / "data" / "care-docs"
OUT_FILE = INFRA_DIR / "out" / "knowledge.json"

# Search data-plane API versions (pinned). GA for indexes/indexers and knowledge sources/bases;
# the knowledge-base MCP endpoint used by Foundry Agent Service is PREVIEW.
SEARCH_GA_API = os.environ.get("SEARCH_GA_API_VERSION", "2026-04-01")
SEARCH_KB_API = os.environ.get("SEARCH_KB_API_VERSION", "2026-04-01")
SEARCH_KB_MCP_API = os.environ.get("SEARCH_KB_MCP_API_VERSION", "2026-08-01-preview")

INDEX, DATASOURCE, INDEXER = "care-docs", "care-docs-ds", "care-docs-indexer"
KNOWLEDGE_SOURCE, KNOWLEDGE_BASE = "care-docs-ks", "care-kb"


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable {name}")
    return value


def retry(fn, what: str, attempts: int = 12, delay: float = 15.0):
    """RBAC assignments made seconds ago can take a few minutes to propagate: retry 401/403s."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except (HttpResponseError, httpx.HTTPStatusError) as exc:
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
            if status in (401, 403) and attempt < attempts:
                print(f"  {what}: HTTP {status} (RBAC propagating?) - retry {attempt}/{attempts} in {delay:.0f}s")
                time.sleep(delay)
                continue
            raise


def upload_docs(credential, account_url: str, container: str) -> list[str]:
    service = BlobServiceClient(account_url=account_url, credential=credential)
    client = service.get_container_client(container)
    names = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        body = path.read_bytes()
        md5 = hashlib.md5(body).digest()  # noqa: S324 - content fingerprint, not security
        blob = client.get_blob_client(path.name)

        def current_md5(b=blob):
            try:
                return b.get_blob_properties().content_settings.content_md5
            except ResourceNotFoundError:
                return None

        if retry(current_md5, f"read {path.name}") == bytearray(md5):
            print(f"  = {path.name} (unchanged)")
            names.append(path.name)
            continue
        retry(lambda: blob.upload_blob(body, overwrite=True, content_settings=ContentSettings(
            content_type="text/markdown; charset=utf-8", content_md5=md5)), f"upload {path.name}")
        print(f"  + {path.name}")
        names.append(path.name)
    return names


class Search:
    """Tiny REST helper: GET-then-PUT with If-Match / If-None-Match for idempotent upserts."""

    def __init__(self, endpoint: str, credential) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.credential = credential

    def _headers(self) -> dict[str, str]:
        token = self.credential.get_token("https://search.azure.com/.default").token
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def get(self, path: str, api: str) -> dict | None:
        r = httpx.get(f"{self.endpoint}/{path}", params={"api-version": api}, headers=self._headers(), timeout=60)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def upsert(self, path: str, body: dict, api: str) -> str:
        existing = retry(lambda: self.get(path, api), f"GET {path}")
        headers = self._headers() | ({"If-Match": "*"} if existing else {"If-None-Match": "*"})
        r = httpx.put(f"{self.endpoint}/{path}", params={"api-version": api}, headers=headers, json=body, timeout=120)
        if r.status_code >= 400:
            print(f"  ! PUT {path} -> {r.status_code}: {r.text[:500]}")
        r.raise_for_status()
        return "updated" if existing else "created"

    def post(self, path: str, api: str) -> int:
        r = httpx.post(f"{self.endpoint}/{path}", params={"api-version": api}, headers=self._headers(), timeout=60)
        return r.status_code


def run_indexer_until_success(search: Search, indexer: str, api: str, attempts: int = 4) -> None:
    """Fresh role assignments (search MI -> storage / Foundry) can make the first run fail: re-run it."""
    for attempt in range(1, attempts + 1):
        search.post(f"indexers/{indexer}/run", api)
        for _ in range(30):
            time.sleep(10)
            last = (search.get(f"indexers/{indexer}/status", api) or {}).get("lastResult") or {}
            if last.get("status") in ("success", "transientFailure", "persistentFailure", "error"):
                break
        failed = last.get("itemsFailed", 0)
        if last.get("status") == "success" and not failed:
            print(f"  indexer {indexer}: success ({last.get('itemsProcessed')} items)")
            return
        print(f"  indexer {indexer}: {last.get('status')} ({failed} failed, {last.get('errorMessage') or ''}) "
              f"- retry {attempt}/{attempts} in 60s")
        time.sleep(60)
        search.post(f"indexers/{indexer}/reset", api)
    print(f"  ! indexer {indexer} still failing - check it in the portal (RBAC propagation?)")


def ensure_fallback_index(search: Search, storage_resource_id: str, container: str) -> None:
    """Classic index + indexer over the blob container (GA). One search document per markdown file."""
    index = {
        "name": INDEX,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "title", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True,
             "analyzer": "en.microsoft"},
            {"name": "url", "type": "Edm.String", "retrievable": True, "filterable": True},
        ],
        "semantic": {"defaultConfiguration": "care-docs-semantic", "configurations": [{
            "name": "care-docs-semantic",
            "prioritizedFields": {"titleField": {"fieldName": "title"},
                                  "prioritizedContentFields": [{"fieldName": "content"}]},
        }]},
    }
    datasource = {
        "name": DATASOURCE, "type": "azureblob",
        # Managed-identity connection string: no storage keys anywhere.
        "credentials": {"connectionString": f"ResourceId={storage_resource_id};"},
        "container": {"name": container},
    }
    indexer = {
        "name": INDEXER, "dataSourceName": DATASOURCE, "targetIndexName": INDEX,
        "parameters": {"configuration": {"parsingMode": "text", "dataToExtract": "contentAndMetadata",
                                         "indexedFileNameExtensions": ".md"}},
        "fieldMappings": [
            {"sourceFieldName": "metadata_storage_path", "targetFieldName": "id",
             "mappingFunction": {"name": "base64Encode"}},
            {"sourceFieldName": "metadata_storage_name", "targetFieldName": "title"},
            {"sourceFieldName": "metadata_storage_path", "targetFieldName": "url"},
        ],
    }
    print(f"  index {INDEX}: {search.upsert(f'indexes/{INDEX}', index, SEARCH_GA_API)}")
    print(f"  datasource {DATASOURCE}: {search.upsert(f'datasources/{DATASOURCE}', datasource, SEARCH_GA_API)}")
    print(f"  indexer {INDEXER}: {search.upsert(f'indexers/{INDEXER}', indexer, SEARCH_GA_API)}")
    run_indexer_until_success(search, INDEXER, SEARCH_GA_API)


def ensure_knowledge_base(search: Search, storage_resource_id: str, container: str) -> None:
    """Foundry IQ: blob knowledge source (auto-generates its own index/indexer) + knowledge base."""
    openai_endpoint = env("FOUNDRY_OPENAI_ENDPOINT")
    knowledge_source = {
        "name": KNOWLEDGE_SOURCE,
        "kind": "azureBlob",
        "description": "Synthetic Lakeside Regional Health Network policies and protocols (fictional).",
        "azureBlobParameters": {
            "connectionString": f"ResourceId={storage_resource_id};",
            "containerName": container,
            "ingestionParameters": {
                "contentExtractionMode": "minimal",
                "disableImageVerbalization": True,
                "embeddingModel": {"kind": "azureOpenAI", "azureOpenAIParameters": {
                    "resourceUri": openai_endpoint, "deploymentId": env("EMBEDDING_DEPLOYMENT"),
                    "modelName": env("EMBEDDING_MODEL")}},
            },
        },
    }
    knowledge_base = {
        "name": KNOWLEDGE_BASE,
        "description": "Care coordination knowledge base (synthetic training content).",
        "knowledgeSources": [{"name": KNOWLEDGE_SOURCE}],
        # The KB's LLM does query planning (search MI needs Cognitive Services User on Foundry).
        "models": [{"kind": "azureOpenAI", "azureOpenAIParameters": {
            "resourceUri": openai_endpoint, "deploymentId": env("CHAT_DEPLOYMENT"), "modelName": env("CHAT_MODEL")}}],
    }
    # These controls are preview-only; the GA KnowledgeBase schema does not define them.
    if SEARCH_KB_API.endswith("-preview"):
        knowledge_base.update({
            "retrievalReasoningEffort": {"kind": "low"},
            "outputMode": "extractiveData",
            "retrievalInstructions": "Prefer the most specific policy section. Documents use section IDs such as FU-3 or PA-3.",
        })
    ks_path = f"knowledgesources/{KNOWLEDGE_SOURCE}"
    existing = search.get(ks_path, SEARCH_KB_API)
    # Some knowledge-source properties are immutable after creation: only PUT when absent or changed.
    wanted = hashlib.sha256(json.dumps(knowledge_source, sort_keys=True).encode()).hexdigest()[:16]
    knowledge_source["description"] += f" [def:{wanted}]"
    if existing and f"[def:{wanted}]" in (existing.get("description") or ""):
        print(f"  knowledge source {KNOWLEDGE_SOURCE}: unchanged")
    else:
        print(f"  knowledge source {KNOWLEDGE_SOURCE}: {search.upsert(ks_path, knowledge_source, SEARCH_KB_API)}")
    kb_path = f"knowledgebases/{KNOWLEDGE_BASE}"
    try:
        print(f"  knowledge base {KNOWLEDGE_BASE}: {search.upsert(kb_path, knowledge_base, SEARCH_KB_API)}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 400:
            raise
        # LLM query planning may not be available for this API version/region: keep the KB, drop the LLM.
        minimal = {k: v for k, v in knowledge_base.items() if k not in ("models", "retrievalInstructions")}
        if SEARCH_KB_API.endswith("-preview"):
            minimal["retrievalReasoningEffort"] = {"kind": "minimal"}
        print(f"  knowledge base {KNOWLEDGE_BASE} (no LLM): "
              f"{search.upsert(kb_path, minimal, SEARCH_KB_API)}")

    deadline = time.time() + 600
    while time.time() < deadline:
        status = search.get(f"{ks_path}/status", SEARCH_KB_API) or {}
        last = status.get("lastSynchronizationState") or {}
        if last.get("endTime"):
            print(f"  ingestion finished: {last.get('status', 'done')}, "
                  f"items processed={last.get('itemUpdatesProcessed')}, failed={last.get('itemsUpdatesFailed')}")
            if last.get("itemsUpdatesFailed"):
                # Usually RBAC propagation (search MI -> embedding model): re-run the generated indexer.
                created = (search.get(ks_path, SEARCH_KB_API) or {}).get("azureBlobParameters", {}).get(
                    "createdResources", {})
                if created.get("indexer"):
                    run_indexer_until_success(search, created["indexer"], SEARCH_GA_API)
            return
        print("  waiting for knowledge source ingestion ...")
        time.sleep(20)
    print("  ! ingestion still running after 10 minutes - continuing (check the portal).")


def main() -> None:
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    account_url, container = env("STORAGE_BLOB_ENDPOINT"), os.environ.get("DOCS_CONTAINER", "care-docs")
    storage_id, search_endpoint = env("STORAGE_ACCOUNT_ID"), env("SEARCH_ENDPOINT").rstrip("/")
    mode = os.environ.get("KNOWLEDGE_MODE", "auto")  # auto | kb | index

    print(f"[1/3] Uploading {len(list(DOCS_DIR.glob('*.md')))} synthetic documents to {container}")
    docs = upload_docs(credential, account_url, container)

    search = Search(search_endpoint, credential)
    print(f"[2/3] Fallback index '{INDEX}' (Search REST {SEARCH_GA_API})")
    ensure_fallback_index(search, storage_id, container)

    effective = "index"
    if mode in ("auto", "kb"):
        print(f"[3/3] Foundry IQ knowledge base '{KNOWLEDGE_BASE}' (Search REST {SEARCH_KB_API})")
        try:
            ensure_knowledge_base(search, storage_id, container)
            effective = "kb"
        except httpx.HTTPStatusError as exc:
            if mode == "kb":
                raise
            print(f"  ! knowledge base API failed ({exc.response.status_code}); FALLBACK to mode 'index'")
    else:
        print("[3/3] KNOWLEDGE_MODE=index: skipping the knowledge base")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "mode": effective,
        "documents": docs,
        "search_endpoint": search_endpoint,
        "index_name": INDEX,
        "knowledge_source": KNOWLEDGE_SOURCE,
        "knowledge_base": KNOWLEDGE_BASE,
        "kb_mcp_endpoint": f"{search_endpoint}/knowledgebases/{KNOWLEDGE_BASE}/mcp?api-version={SEARCH_KB_MCP_API}",
        "docs_fingerprint": base64.b16encode(hashlib.sha256(
            b"".join(p.read_bytes() for p in sorted(DOCS_DIR.glob("*.md")))).digest()).decode()[:16],
    }
    OUT_FILE.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_FILE.relative_to(INFRA_DIR)} (mode={effective})")


if __name__ == "__main__":
    main()
