# Participant-facing APIs (CONTRACT §2). Every policy lives in ./policies/*.xml (templatefile).
# API version 2025-09-01-preview is required for MCP servers/tools (PREVIEW API version).
# Policies use format "xml": the files are well-formed XML, so C# generics in policy expressions
# are written XML-encoded (As&lt;JObject&gt;) and decoded by APIM.

locals {
  api_version = "2025-09-01-preview"
  apis        = "Microsoft.ApiManagement/service/apis@${local.api_version}"
  methods     = ["GET", "POST", "PUT", "PATCH", "DELETE"]
  policies    = "${path.module}/policies"

  # MCP tools are generated from the committed OpenAPI spec: operationId == tool name, and the
  # operation description (written for LLMs) becomes the MCP tool description.
  openapi = jsondecode(file(var.care_tools_openapi_path))
  tools = merge([
    for path, ops in local.openapi.paths : {
      for method, op in ops : op.operationId => { description = op.description, summary = op.summary }
    }
  ]...)

  # ---- A2A wiring --------------------------------------------------------------------------
  native           = var.a2a_mode == "native_foundry"
  adapter_url      = coalesce(var.a2a_adapter_url, "https://adapter-not-deployed.invalid")
  foundry_protocol = "https://${var.foundry_account_name}.services.ai.azure.com/api/projects/${var.foundry_project_name}/agents/care-knowledge-agent/endpoint/protocols"
  public_a2a_url   = "${var.gateway_url}/a2a/care-knowledge"
  a2a = {
    card_backend_url    = local.native ? "${local.foundry_protocol}/a2a/agentCard/v1.0" : "${local.adapter_url}/.well-known/agent-card.json"
    jsonrpc_backend_url = local.native ? "${local.foundry_protocol}/a2a" : local.adapter_url
    http_backend_base   = local.native ? local.foundry_protocol : local.adapter_url
    http_card_path      = local.native ? "/a2a/agentCard/v1.0" : "/.well-known/agent-card.json"
    http_jsonrpc_path   = local.native ? "/a2a" : "/"
    replace_from        = local.native ? "${local.foundry_protocol}/a2a" : local.adapter_url
  }
  # Exactly one of the two A2A API flavours exists.
  a2a_api_id = one(concat(azapi_resource.a2a_agent[*].id, azapi_resource.a2a_http[*].id))

  telemetry_config = jsonencode({
    connectionString   = "InstrumentationKey=${var.telemetry_instrumentation_key};IngestionEndpoint=${var.gateway_url}/telemetry/"
    foundryProjectName = var.foundry_project_name
    chatModel          = var.chat_model
    judgeModel         = var.judge_model
  })
}

# ============================================================================================
# /openai — models (backend: Foundry, managed identity; subscription key header "api-key")
# ============================================================================================
resource "azapi_resource" "openai" {
  type      = local.apis
  name      = "openai"
  parent_id = var.apim_id
  body = {
    properties = {
      displayName                   = "Foundry models (Azure OpenAI-compatible)"
      description                   = "Chat, judge and embedding models. Token-limited and metered per participant."
      path                          = "openai"
      protocols                     = ["https"]
      type                          = "http"
      subscriptionRequired          = true
      subscriptionKeyParameterNames = { header = "api-key", query = "api-key" }
    }
  }
}

resource "azapi_resource" "openai_ops" {
  for_each  = toset(local.methods)
  type      = "Microsoft.ApiManagement/service/apis/operations@${local.api_version}"
  name      = "all-${lower(each.key)}"
  parent_id = azapi_resource.openai.id
  body = {
    properties = { displayName = "${each.key} /*", method = each.key, urlTemplate = "/*", templateParameters = [] }
  }
}

resource "azapi_resource" "openai_policy" {
  type      = "Microsoft.ApiManagement/service/apis/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.openai.id
  body = {
    properties = {
      format = "xml"
      value = templatefile("${local.policies}/openai.xml", {
        tokens_per_minute      = var.token_limit_tpm
        content_safety         = var.enable_content_safety
        openai_backend         = var.backends["openai"]
        content_safety_backend = var.backends["content_safety"]
      })
    }
  }
  depends_on = [azapi_resource.openai_ops]
}

# ============================================================================================
# /care-tools-api (REST, backing API)  +  /care-tools/mcp (MCP server with 7 tools)
# ============================================================================================
resource "azapi_resource" "care_tools_api" {
  type      = local.apis
  name      = "care-tools-api"
  parent_id = var.apim_id
  body = {
    properties = {
      displayName          = "Care Tools API (synthetic, backing REST API)"
      path                 = "care-tools-api"
      protocols            = ["https"]
      type                 = "http"
      serviceUrl           = "https://${var.care_tools_fqdn}"
      subscriptionRequired = true
      # Import the committed OpenAPI spec; APIM names each operation after its operationId.
      format = "openapi+json"
      value  = file(var.care_tools_openapi_path)
    }
  }
  # format/value are import-only inputs and are not returned by GET.
  ignore_missing_property = true
}

resource "azapi_resource" "care_tools_api_policy" {
  type      = "Microsoft.ApiManagement/service/apis/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.care_tools_api.id
  body = {
    properties = { format = "xml", value = templatefile("${local.policies}/care-tools-api.xml", { secret_nv = var.shared_secret_nv }) }
  }
}

resource "azapi_resource" "care_tools_mcp" {
  type      = local.apis
  name      = "care-tools"
  parent_id = var.apim_id
  body = {
    properties = {
      type                 = "mcp"
      displayName          = "Care tools (MCP server)"
      description          = "Mock clinical tools for the fictional Lakeside Regional Health Network. Synthetic data only; not clinical advice."
      path                 = "care-tools"
      protocols            = ["https"]
      subscriptionRequired = true
    }
  }
}

resource "azapi_resource" "care_tools_mcp_tools" {
  for_each  = local.tools
  type      = "Microsoft.ApiManagement/service/apis/tools@${local.api_version}"
  name      = each.key
  parent_id = azapi_resource.care_tools_mcp.id
  body = {
    properties = {
      displayName = each.key
      description = substr(each.value.description, 0, 1000)
      # Full ARM ID of the backing REST operation (operation name == OpenAPI operationId).
      operationId = "${azapi_resource.care_tools_api.id}/operations/${each.key}"
    }
  }
}

resource "azapi_resource" "care_tools_mcp_policy" {
  type      = "Microsoft.ApiManagement/service/apis/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.care_tools_mcp.id
  body = {
    properties = { format = "xml", value = templatefile("${local.policies}/care-tools-mcp.xml", { secret_nv = var.shared_secret_nv }) }
  }
  depends_on = [azapi_resource.care_tools_mcp_tools]
}

# ============================================================================================
# /a2a/care-knowledge — A2A to the base agent
# ============================================================================================
# Preferred: APIM "A2A agent API" (GA feature). Its ARM shape (type/apiType "a2a", agent,
# a2aProperties, jsonRpcProperties) is not yet in the published schema, hence no schema validation.
# The card URL requires Entra ID, so it is configured explicitly instead of being imported.
resource "azapi_resource" "a2a_agent" {
  count     = var.a2a_api_kind == "a2a" ? 1 : 0
  type      = local.apis
  name      = "care-knowledge-a2a"
  parent_id = var.apim_id
  body = {
    properties = {
      type        = "a2a"
      apiType     = "a2a"
      isAgent     = true
      displayName = "Care Knowledge Agent (A2A)"
      description = "A2A JSON-RPC endpoint of the Foundry prompt agent care-knowledge-agent. Synthetic data only."
      path        = "a2a/care-knowledge"
      protocols   = ["https"]
      agent = {
        # logged as gen_ai.agent.id
        id           = "care-knowledge-agent"
        name         = "Care Knowledge Agent"
        providerName = local.native ? "Microsoft Foundry Agent Service" : "Agent Framework A2A adapter"
      }
      a2aProperties = {
        agentCardPath       = "/.well-known/agent-card.json"
        agentCardBackendUrl = local.a2a.card_backend_url
      }
      jsonRpcProperties = {
        path       = "/"
        backendUrl = local.a2a.jsonrpc_backend_url
      }
      subscriptionRequired          = true
      subscriptionKeyParameterNames = { header = "Ocp-Apim-Subscription-Key", query = "subscription-key" }
    }
  }
  schema_validation_enabled = false
  ignore_missing_property   = true
}

# FALLBACK flavour: plain HTTP API with explicit card + JSON-RPC operations (a2a_apim_api_kind = "http").
resource "azapi_resource" "a2a_http" {
  count     = var.a2a_api_kind == "http" ? 1 : 0
  type      = local.apis
  name      = "care-knowledge-a2a"
  parent_id = var.apim_id
  body = {
    properties = {
      type                 = "http"
      displayName          = "Care Knowledge Agent (A2A over HTTP API)"
      path                 = "a2a/care-knowledge"
      protocols            = ["https"]
      serviceUrl           = local.a2a.http_backend_base
      subscriptionRequired = true
    }
  }
}

resource "azapi_resource" "a2a_http_card_op" {
  count     = var.a2a_api_kind == "http" ? 1 : 0
  type      = "Microsoft.ApiManagement/service/apis/operations@${local.api_version}"
  name      = "agent-card"
  parent_id = azapi_resource.a2a_http[0].id
  body = {
    properties = { displayName = "Agent card", method = "GET", urlTemplate = "/.well-known/agent-card.json", templateParameters = [] }
  }
}

resource "azapi_resource" "a2a_http_card_policy" {
  count     = var.a2a_api_kind == "http" ? 1 : 0
  type      = "Microsoft.ApiManagement/service/apis/operations/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.a2a_http_card_op[0].id
  body = {
    properties = {
      format = "xml"
      value = templatefile("${local.policies}/a2a-card-operation.xml", {
        card_path    = local.a2a.http_card_path
        replace_from = local.a2a.replace_from
        replace_to   = local.public_a2a_url
      })
    }
  }
}

resource "azapi_resource" "a2a_http_jsonrpc_op" {
  count     = var.a2a_api_kind == "http" ? 1 : 0
  type      = "Microsoft.ApiManagement/service/apis/operations@${local.api_version}"
  name      = "jsonrpc"
  parent_id = azapi_resource.a2a_http[0].id
  body = {
    properties = { displayName = "A2A JSON-RPC", method = "POST", urlTemplate = "/", templateParameters = [] }
  }
}

resource "azapi_resource" "a2a_http_jsonrpc_policy" {
  count     = var.a2a_api_kind == "http" ? 1 : 0
  type      = "Microsoft.ApiManagement/service/apis/operations/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.a2a_http_jsonrpc_op[0].id
  body = {
    properties = {
      format = "xml"
      value  = templatefile("${local.policies}/a2a-jsonrpc-operation.xml", { jsonrpc_path = local.a2a.http_jsonrpc_path })
    }
  }
}

resource "azapi_resource" "a2a_policy" {
  type      = "Microsoft.ApiManagement/service/apis/policies@${local.api_version}"
  name      = "policy"
  parent_id = local.a2a_api_id
  body = {
    properties = {
      format = "xml"
      value = templatefile("${local.policies}/a2a.xml", {
        adapter          = !local.native
        http_kind        = var.a2a_api_kind == "http"
        backend_base_url = local.a2a.http_backend_base
        secret_nv        = var.shared_secret_nv
      })
    }
  }
}

# ============================================================================================
# /foundry — Foundry project data-plane proxy with an operation allowlist
# ============================================================================================
resource "azapi_resource" "foundry" {
  type      = local.apis
  name      = "foundry"
  parent_id = var.apim_id
  body = {
    properties = {
      displayName          = "Foundry project data plane (allowlisted)"
      description          = "Evaluations, datasets, red teams, agent reads and OpenAI evals/responses for the workshop project."
      path                 = "foundry"
      protocols            = ["https"]
      type                 = "http"
      serviceUrl           = "https://${var.foundry_account_name}.services.ai.azure.com"
      subscriptionRequired = true
    }
  }
}

resource "azapi_resource" "foundry_ops" {
  for_each  = toset(local.methods)
  type      = "Microsoft.ApiManagement/service/apis/operations@${local.api_version}"
  name      = "all-${lower(each.key)}"
  parent_id = azapi_resource.foundry.id
  body = {
    properties = { displayName = "${each.key} /*", method = each.key, urlTemplate = "/*", templateParameters = [] }
  }
}

resource "azapi_resource" "foundry_policy" {
  type      = "Microsoft.ApiManagement/service/apis/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.foundry.id
  body = {
    properties = {
      format = "xml"
      value  = templatefile("${local.policies}/foundry.xml", { project = lower(var.foundry_project_name), project_backend = var.backends["project"] })
    }
  }
  depends_on = [azapi_resource.foundry_ops]
}

# ============================================================================================
# /telemetry — Application Insights ingestion proxy + GET /telemetry/config
# ============================================================================================
resource "azapi_resource" "telemetry" {
  type      = local.apis
  name      = "telemetry"
  parent_id = var.apim_id
  body = {
    properties = {
      displayName = "Telemetry (Application Insights ingestion proxy)"
      path        = "telemetry"
      protocols   = ["https"]
      type        = "http"
      serviceUrl  = var.telemetry_ingestion_endpoint
      # FALLBACK (telemetry_require_subscription_key = false): anonymous but iKey-filtered + rate-limited.
      subscriptionRequired = var.telemetry_require_subscription_key
    }
  }
}

resource "azapi_resource" "telemetry_ops" {
  for_each = {
    "track-v2-1" = { method = "POST", url = "/v2.1/track" }
    "track-v2"   = { method = "POST", url = "/v2/track" }
    "config"     = { method = "GET", url = "/config" }
  }
  type      = "Microsoft.ApiManagement/service/apis/operations@${local.api_version}"
  name      = each.key
  parent_id = azapi_resource.telemetry.id
  body = {
    properties = { displayName = "${each.value.method} ${each.value.url}", method = each.value.method, urlTemplate = each.value.url, templateParameters = [] }
  }
}

resource "azapi_resource" "telemetry_policy" {
  type      = "Microsoft.ApiManagement/service/apis/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.telemetry.id
  body = {
    properties = {
      format = "xml"
      value = templatefile("${local.policies}/telemetry.xml", {
        anonymous      = !var.telemetry_require_subscription_key
        ikey           = var.telemetry_instrumentation_key
        max_body_bytes = 3145728
      })
    }
  }
  depends_on = [azapi_resource.telemetry_ops]
}

resource "azapi_resource" "telemetry_config_policy" {
  type      = "Microsoft.ApiManagement/service/apis/operations/policies@${local.api_version}"
  name      = "policy"
  parent_id = azapi_resource.telemetry_ops["config"].id
  body = {
    properties = {
      format = "xml"
      value  = templatefile("${local.policies}/telemetry-config.xml", { config_json = local.telemetry_config })
    }
  }
}

# Don't trace the trace pipeline: sample 0 % of successful /telemetry calls (errors are still logged).
resource "azapi_resource" "telemetry_diagnostic" {
  type      = "Microsoft.ApiManagement/service/apis/diagnostics@${local.api_version}"
  name      = "applicationinsights"
  parent_id = azapi_resource.telemetry.id
  body = {
    properties = {
      loggerId                = var.appinsights_logger_id
      alwaysLog               = "allErrors"
      httpCorrelationProtocol = "W3C"
      sampling                = { samplingType = "fixed", percentage = 0 }
    }
  }
}

# ============================================================================================
# Product bindings (the participant product exposes exactly the contract routes)
# ============================================================================================
locals {
  product_apis = merge(
    {
      "openai"     = azapi_resource.openai.name
      "care-tools" = azapi_resource.care_tools_mcp.name
      "a2a"        = "care-knowledge-a2a"
      "foundry"    = azapi_resource.foundry.name
      "telemetry"  = azapi_resource.telemetry.name
    },
    var.care_tools_rest_in_product ? { "care-tools-api" = azapi_resource.care_tools_api.name } : {}
  )
}

# Product/API associations expose HEAD, not GET. AzureRM uses CheckEntityExists for reads.
resource "azurerm_api_management_product_api" "product_api" {
  for_each            = local.product_apis
  api_name            = each.value
  product_id          = basename(var.product_id)
  api_management_name = var.apim_name
  resource_group_name = var.resource_group_name
  depends_on = [
    azapi_resource.openai, azapi_resource.care_tools_mcp, azapi_resource.a2a_agent, azapi_resource.a2a_http,
    azapi_resource.foundry, azapi_resource.telemetry, azapi_resource.care_tools_api,
  ]
}
