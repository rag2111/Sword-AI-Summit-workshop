# Versions are pinned once in the root module (infra/versions.tf); modules only declare sources.
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    random  = { source = "hashicorp/random" }
  }
}
