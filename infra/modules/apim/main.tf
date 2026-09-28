# API Management: the single front door for participants (models, MCP tools, A2A, Foundry data plane,
# telemetry). Service uses the GA API 2024-05-01; child resources use 2025-09-01-preview, the first
# version with MCP servers and LLM logging (PREVIEW API version; features themselves are GA).

locals {
  apim_api = "2025-09-01-preview"
}

resource "azapi_resource" "service" {
  type      = "Microsoft.ApiManagement/service@2024-05-01"
  name      = var.name
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    sku = { name = var.sku, capacity = var.capacity }
    properties = {
      publisherName  = var.publisher_name
      publisherEmail = var.publisher_email
    }
  }
  response_export_values = ["properties.gatewayUrl"]

  timeouts {
    # classic tiers (Developer/Standard/Premium) can take 30-60+ minutes
    create = "120m"
    update = "120m"
    delete = "60m"
  }
}

# ---- Observability ----------------------------------------------------------------------------
resource "azapi_resource" "logger_appinsights" {
  type      = "Microsoft.ApiManagement/service/loggers@${local.apim_api}"
  name      = "appinsights"
  parent_id = azapi_resource.service.id
  body = {
    properties = {
      loggerType  = "applicationInsights"
      resourceId  = var.app_insights_id
      isBuffered  = true
      description = "Workshop Application Insights (traces, token metrics)"
    }
  }
  sensitive_body = {
    properties = { credentials = { connectionString = var.app_insights_connection_string } }
  }
}

# APIM creates this built-in logger; update it rather than attempting to create it.
resource "azapi_update_resource" "logger_azuremonitor" {
  type      = "Microsoft.ApiManagement/service/loggers@${local.apim_api}"
  name      = "azuremonitor"
  parent_id = azapi_resource.service.id
  body = {
    properties = { loggerType = "azureMonitor", isBuffered = true }
  }
}

locals {
  # MCP guidance: with global diagnostics on, log 0 bytes of frontend response bodies.
  no_bodies = {
    frontend = {
      request  = { headers = ["traceparent", "x-ms-client-request-id"], body = { bytes = 0 } }
      response = { headers = [], body = { bytes = 0 } }
    }
    backend = {
      request  = { headers = ["x-participant-id", "traceparent"], body = { bytes = 0 } }
      response = { headers = [], body = { bytes = 0 } }
    }
  }
}

# Application Insights diagnostic: request spans correlated with the caller's W3C trace context.
resource "azapi_resource" "diag_appinsights" {
  type      = "Microsoft.ApiManagement/service/diagnostics@${local.apim_api}"
  name      = "applicationinsights"
  parent_id = azapi_resource.service.id
  body = {
    properties = merge(local.no_bodies, {
      loggerId                = azapi_resource.logger_appinsights.id
      alwaysLog               = "allErrors"
      httpCorrelationProtocol = "W3C"
      verbosity               = "information"
      logClientIp             = true
      # required for llm-emit-token-metric custom metrics
      metrics             = true
      operationNameFormat = "Name"
      sampling            = { samplingType = "fixed", percentage = 100 }
    })
  }
}

# APIM creates this built-in diagnostic; update it with LLM message logging instead of recreating it.
# Logs flow to ApiManagementGatewayLlmLog and power the portal's "Language models" analytics.
resource "azapi_update_resource" "diag_azuremonitor" {
  type      = "Microsoft.ApiManagement/service/diagnostics@${local.apim_api}"
  name      = "azuremonitor"
  parent_id = azapi_resource.service.id
  body = {
    properties = merge(local.no_bodies, {
      loggerId    = azapi_update_resource.logger_azuremonitor.id
      logClientIp = true
      verbosity   = "information"
      sampling    = { samplingType = "fixed", percentage = 100 }
      largeLanguageModel = {
        logs      = "enabled"
        requests  = { messages = "all", maxSizeInBytes = 32768 }
        responses = { messages = "all", maxSizeInBytes = 32768 }
      }
    })
  }
}

resource "azurerm_monitor_diagnostic_setting" "apim" {
  name                       = "apim-to-log-analytics"
  target_resource_id         = azapi_resource.service.id
  log_analytics_workspace_id = var.log_analytics_workspace_id
  # resource-specific tables, e.g. ApiManagementGatewayLlmLog
  log_analytics_destination_type = "Dedicated"

  enabled_log {
    category_group = "allLogs"
  }
  enabled_metric {
    category = "AllMetrics"
  }
}

# ---- Global policy, named values, product ---------------------------------------------------
# The service already has a default global policy, including on a fresh deployment.
resource "azapi_update_resource" "global_policy" {
  type      = "Microsoft.ApiManagement/service/policies@${local.apim_api}"
  name      = "policy"
  parent_id = azapi_resource.service.id
  body = {
    properties = { format = "xml", value = file("${path.module}/policies/global.xml") }
  }
}

resource "azapi_resource" "nv_backend_secret" {
  type      = "Microsoft.ApiManagement/service/namedValues@${local.apim_api}"
  name      = "backend-shared-secret"
  parent_id = azapi_resource.service.id
  body = {
    properties = { displayName = "backend-shared-secret", secret = true }
  }
  sensitive_body = {
    properties = { value = var.backend_shared_secret }
  }
}

resource "azapi_resource" "product" {
  type      = "Microsoft.ApiManagement/service/products@${local.apim_api}"
  name      = "workshop-participants"
  parent_id = azapi_resource.service.id
  body = {
    properties = {
      displayName          = "Workshop participants"
      description          = "One subscription per participant. Training use only; synthetic data."
      subscriptionRequired = true
      approvalRequired     = false
      state                = "published"
    }
  }
}

# ---- Backends --------------------------------------------------------------------------------
resource "azapi_resource" "backend_openai" {
  type      = "Microsoft.ApiManagement/service/backends@${local.apim_api}"
  name      = "foundry-openai"
  parent_id = azapi_resource.service.id
  body = {
    properties = {
      description = "Foundry models (Azure OpenAI-compatible endpoint)"
      url         = "https://${var.foundry_account_name}.openai.azure.com/openai"
      protocol    = "http"
    }
  }
}

resource "azapi_resource" "backend_project" {
  type      = "Microsoft.ApiManagement/service/backends@${local.apim_api}"
  name      = "foundry-project"
  parent_id = azapi_resource.service.id
  body = {
    properties = {
      description = "Foundry project data plane"
      url         = "https://${var.foundry_account_name}.services.ai.azure.com"
      protocol    = "http"
    }
  }
}

# Content Safety (llm-content-safety policy) authenticates with APIM's managed identity.
resource "azapi_resource" "backend_content_safety" {
  count     = var.enable_content_safety ? 1 : 0
  type      = "Microsoft.ApiManagement/service/backends@${local.apim_api}"
  name      = "content-safety"
  parent_id = azapi_resource.service.id
  body = {
    properties = {
      description = "Azure AI Content Safety on the Foundry resource"
      url         = "https://${var.foundry_account_name}.cognitiveservices.azure.com"
      protocol    = "http"
      credentials = { managedIdentity = { resource = "https://cognitiveservices.azure.com" } }
    }
  }
  schema_validation_enabled = false
}
