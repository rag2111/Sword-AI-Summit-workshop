# Preview features — infra (Deliverable 1)

Status verified September 2026. "GA feature / preview API" means the capability is generally available
but the ARM API version that exposes it is a preview version.

| Feature | Where used | Status (GA/preview + API version) | Fallback |
|---|---|---|---|
| Foundry incoming A2A (agent endpoint A2A protocol + agent card) | `scripts/create_base_agent.py` (`project.agents.update_details`), native backend of `/a2a/care-knowledge` | **Preview** (A2A protocol 1.0 GA on the endpoint, 0.3 preview); Foundry REST `v1`, `azure-ai-projects==2.7.0` | `a2a_mode = "adapter"` (Agent Framework A2A adapter on Container Apps) |
| APIM A2A agent API (`type`/`apiType = "a2a"`, `agent`, `a2aProperties`, `jsonRpcProperties`) | `modules/apim_apis` `azapi_resource.a2a_agent` | Feature **GA**; ARM shape not yet in the published `2025-09-01-preview` schema (schema validation disabled) | `a2a_apim_api_kind = "http"` (plain HTTP API with card rewrite + JSON-RPC operation) |
| APIM MCP server from REST API + `apis/tools` | `modules/apim_apis` (`care-tools`, 7 tools) | Feature **GA**; ARM `Microsoft.ApiManagement/service/apis@2025-09-01-preview` (preview API version) | Portal: *MCP Servers → Expose an API as an MCP server* (same REST API and operations) |
| APIM LLM message logging (`largeLanguageModel` on diagnostics) | `modules/apim` `diag_azuremonitor` | **Preview API** `2025-09-01-preview` | Remove the `largeLanguageModel` block; App Insights request telemetry and token metrics still work |
| APIM child resources (loggers, diagnostics, named values, product, backends, APIs, policies) | `modules/apim`, `modules/apim_apis` | **Preview API** `2025-09-01-preview`; service itself GA `2024-05-01` | `2024-05-01` for everything except MCP/LLM logging |
| `llm-token-limit`, `llm-emit-token-metric`, `llm-content-safety` policies | `modules/apim_apis/policies/openai.xml` | **GA** (extra token categories such as cached/reasoning are preview) | `azure-openai-token-limit` / `azure-openai-emit-token-metric` |
| Content Safety backend with managed-identity credentials | `modules/apim` `backend_content_safety` (only if `enable_content_safety = true`) | **Preview API** `2025-09-01-preview`, schema validation disabled | Keep `enable_content_safety = false` (default) |
| Foundry IQ knowledge source (`azureBlob`) + knowledge base `care-kb` | `scripts/seed_knowledge.py` | Search REST **GA `2026-04-01`** with model configuration; `outputMode`, `retrievalInstructions`, and `retrievalReasoningEffort` are sent only when `SEARCH_KB_API_VERSION` explicitly selects a preview API | Script retries without models (also sets `retrievalReasoningEffort: minimal` for preview only); then `knowledge_mode = "index"` |
| Knowledge base MCP endpoint (`/knowledgebases/care-kb/mcp`) | Base agent MCP tool | **Preview** Search REST `2026-08-01-preview` | `knowledge_mode = "index"` → Azure AI Search tool on index `care-docs` (GA) |
| `RemoteTool` project connection with `ProjectManagedIdentity` | `scripts/create_base_agent.py` (`care-kb-mcp`) | **Preview** ARM `2025-10-01-preview` | `knowledge_mode = "index"` (uses GA `CognitiveSearch` connection `care-search`) |
| Foundry AI-gateway connection (category `ApiManagement`, model `apim-gateway/<deployment>`) | `main.tf` `azapi_resource.apim_gateway_connection`, base agent model | **Preview**; ARM `2026-07-15-preview` | `base_agent_model_route = "direct"`; `auto` falls back automatically after a failed test call |
| Search service `knowledgeRetrieval` billing plan | `modules/search_storage` | **Preview** management API `2026-03-01-preview` | GA `2025-05-01` without the property; choose the plan in the portal (Premium features) |
| Agent Framework A2A hosting (`agent-framework-hosting`, `agent-framework-hosting-a2a` `1.0.0a260730`) | `apps/a2a_adapter` (fallback only) | **Pre-release** packages (pinned); `a2a-sdk==1.1.5` GA | Native Foundry A2A (default); or a plain `a2a-sdk` server |
| Foundry prompt agents (`project.agents.create_version`, `PromptAgentDefinition`, `MCPTool`, `AzureAISearchTool`) | `scripts/create_base_agent.py` | **GA** (`azure-ai-projects==2.7.0`, REST `v1`) | — |
| Foundry account/project/deployments/connections (AppInsights, CognitiveSearch, AzureStorageAccount) | `modules/foundry` | **GA** `2026-05-01` (supported by pinned AzAPI schema) | — |
