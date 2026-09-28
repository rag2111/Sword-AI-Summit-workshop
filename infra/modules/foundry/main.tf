# Microsoft Foundry (new model): a Cognitive Services account of kind AIServices with project
# management enabled, plus ONE child project. No Microsoft.MachineLearningServices hub/workspace.
# API version 2026-05-01 is supported by the pinned AzAPI provider for these resource types.

resource "azapi_resource" "account" {
  type      = "Microsoft.CognitiveServices/accounts@2026-05-01"
  name      = var.account_name
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    kind = "AIServices"
    sku  = { name = "S0" }
    properties = {
      allowProjectManagement = true
      customSubDomainName    = var.account_name
      publicNetworkAccess    = "Enabled"
      # Keys disabled: every caller (APIM, Search, scripts) uses Entra ID / managed identity.
      disableLocalAuth = true
    }
  }
}

resource "azapi_resource" "project" {
  type      = "Microsoft.CognitiveServices/accounts/projects@2026-05-01"
  name      = var.project_name
  parent_id = azapi_resource.account.id
  location  = var.location
  tags      = var.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    properties = {
      displayName = var.project_name
      description = "Care Coordination workshop project (synthetic data only)."
    }
  }
}

# Region/model availability and quota are the #1 deployment failure: see README "Region choice".
resource "azapi_resource" "deployment" {
  for_each  = { for d in var.model_deployments : d.name => d }
  type      = "Microsoft.CognitiveServices/accounts/deployments@2026-05-01"
  name      = each.value.name
  parent_id = azapi_resource.account.id

  body = {
    sku = { name = each.value.sku, capacity = each.value.capacity }
    properties = {
      model = { format = "OpenAI", name = each.value.model, version = each.value.version }
      # pinned model versions: eval results stay comparable
      versionUpgradeOption = "NoAutoUpgrade"
      raiPolicyName        = "Microsoft.DefaultV2"
    }
  }

  # The account accepts one deployment operation at a time; parallel PUTs get 409 and are retried.
  retry = {
    error_message_regex  = ["RequestConflict", "AnotherOperationInProgress", "Conflict", "429"]
    interval_seconds     = 15
    max_interval_seconds = 120
  }
  depends_on = [azapi_resource.project]
}

# --- Project connections ---------------------------------------------------------------------
# Application Insights: enables Foundry portal tracing and agent/evaluation telemetry.
resource "azapi_resource" "conn_app_insights" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-01"
  name      = "appinsights"
  parent_id = azapi_resource.project.id
  body = {
    properties = {
      category      = "AppInsights"
      target        = var.app_insights_id
      authType      = "ApiKey"
      isSharedToAll = false
      metadata      = { ApiType = "Azure", ResourceId = var.app_insights_id }
    }
  }
  sensitive_body = {
    properties = { credentials = { key = var.app_insights_connection_string } }
  }
}

# Azure AI Search (Entra ID via the project's managed identity): used by the FALLBACK search tool.
resource "azapi_resource" "conn_search" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-01"
  name      = "care-search"
  parent_id = azapi_resource.project.id
  body = {
    properties = {
      category      = "CognitiveSearch"
      target        = var.search_endpoint
      authType      = "AAD"
      isSharedToAll = false
      metadata      = { ApiType = "Azure", ResourceId = var.search_service_id, location = var.location }
    }
  }
}

# Storage (Entra ID): lets the portal browse the source documents of the knowledge base.
resource "azapi_resource" "conn_storage" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-01"
  name      = "care-storage"
  parent_id = azapi_resource.project.id
  body = {
    properties = {
      category      = "AzureStorageAccount"
      target        = var.storage_blob_endpoint
      authType      = "AAD"
      isSharedToAll = false
      metadata      = { ApiType = "Azure", ResourceId = var.storage_account_id, location = var.location }
    }
  }
}
