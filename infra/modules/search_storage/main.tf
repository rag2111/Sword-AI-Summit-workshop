# Knowledge storage (blob container with the 12 synthetic documents) and Azure AI Search.
# azapi is used for pure-ARM control: shared-key access is disabled on storage (Entra only), and the
# Search `knowledgeRetrieval` billing property only exists in a preview management API version.

resource "azapi_resource" "storage" {
  type      = "Microsoft.Storage/storageAccounts@2025-01-01"
  name      = var.storage_account_name
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags

  body = {
    kind = "StorageV2"
    sku  = { name = "Standard_LRS" }
    properties = {
      accessTier            = "Hot"
      allowBlobPublicAccess = false
      # Entra ID only: no storage keys exist to leak
      allowSharedKeyAccess         = false
      defaultToOAuthAuthentication = true
      minimumTlsVersion            = "TLS1_2"
      supportsHttpsTrafficOnly     = true
      publicNetworkAccess          = "Enabled"
    }
  }
  response_export_values = ["properties.primaryEndpoints.blob"]
}

resource "azapi_resource" "docs_container" {
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01"
  name      = var.docs_container_name
  parent_id = "${azapi_resource.storage.id}/blobServices/default"
  body = {
    properties = { publicAccess = "None" }
  }
}

# PREVIEW management API (2026-03-01-preview) for `knowledgeRetrieval` (agentic retrieval billing plan).
# Fallback: use 2025-05-01 (GA) without knowledgeRetrieval and select the plan in the portal
# (Search service > Settings > Premium features).
resource "azapi_resource" "search" {
  type      = "Microsoft.Search/searchServices@2026-03-01-preview"
  name      = var.search_service_name
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    sku = { name = var.search_sku }
    properties = {
      replicaCount   = 1
      partitionCount = 1
      hostingMode    = "default"
      # semantic ranker (required for good agentic retrieval)
      semanticSearch     = "standard"
      knowledgeRetrieval = var.knowledge_retrieval_plan
      disableLocalAuth   = false
      authOptions = {
        # Entra ID tokens for the scripts and managed identities; API keys stay possible for break-glass.
        aadOrApiKey = { aadAuthFailureMode = "http401WithBearerChallenge" }
      }
    }
  }
  schema_validation_enabled = false
}
