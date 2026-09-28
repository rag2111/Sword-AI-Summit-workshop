# Versions are pinned once in the root module (infra/versions.tf); modules only declare sources.
terraform {
  required_providers {
    azapi   = { source = "Azure/azapi" }
    azurerm = { source = "hashicorp/azurerm" }
  }
}
