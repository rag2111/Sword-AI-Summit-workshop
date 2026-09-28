# Versions are pinned once in the root module (infra/versions.tf); modules only declare sources.
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    local   = { source = "hashicorp/local" }
    random  = { source = "hashicorp/random" }
  }
}
