# Pinned toolchain (verified September 2026):
#   azurerm 5.7.0 (2026-09-24), azapi 2.13.0, random 3.9.1, local 2.9.1.
# azurerm covers the "classic" resources; azapi covers everything azurerm lacks or lags on
# (Foundry accounts/projects/connections, APIM MCP/A2A APIs, APIM LLM logging, Search knowledgeRetrieval).
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 5.7.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "= 2.13.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "= 3.9.1"
    }
    local = {
      source  = "hashicorp/local"
      version = "= 2.9.1"
    }
  }
}

provider "azurerm" {
  subscription_id = var.subscription_id

  # azurerm 5.x no longer auto-registers resource providers; register exactly what this stack uses.
  resource_providers_to_register = [
    "Microsoft.ApiManagement",
    "Microsoft.App",
    "Microsoft.CognitiveServices",
    "Microsoft.ContainerRegistry",
    "Microsoft.Insights",
    "Microsoft.ManagedIdentity",
    "Microsoft.OperationalInsights",
    "Microsoft.Search",
    "Microsoft.Storage",
  ]

  features {
    resource_group {
      # Post-deploy scripts create data-plane objects Terraform doesn't track; allow clean destroy.
      prevent_deletion_if_contains_resources = false
    }
  }
}

provider "azapi" {
  subscription_id = var.subscription_id
}
