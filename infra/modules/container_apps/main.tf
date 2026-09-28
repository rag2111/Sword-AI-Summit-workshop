# Container Apps hosting for the mock clinical tools (always) and the A2A adapter (fallback only).
# Images are built in ACR with `az acr build` (no local Docker needed) and tagged with a hash of the
# source folder, so a code change triggers a rebuild and a new revision.

locals {
  apps_dir = abspath("${path.module}/../../apps")
  sources = {
    tools   = "${local.apps_dir}/care_tools_backend"
    adapter = "${local.apps_dir}/a2a_adapter"
  }
  source_hash = {
    for k, dir in local.sources : k => substr(sha1(join("", [
      for f in sort(fileset(dir, "**")) : filesha1("${dir}/${f}") if !strcontains(f, "__pycache__") && !startswith(f, ".venv")
    ])), 0, 12)
  }
  tools_image   = "${azurerm_container_registry.this.login_server}/care-tools-backend:${local.source_hash.tools}"
  adapter_image = "${azurerm_container_registry.this.login_server}/care-knowledge-a2a:${local.source_hash.adapter}"
  acr_pull_role = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
  foundry_user  = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
}

data "azurerm_subscription" "current" {}

resource "azurerm_container_registry" "this" {
  name                = var.registry_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  # pulls use managed identity
  admin_enabled = false
  tags          = var.tags
}

resource "azurerm_container_app_environment" "this" {
  name                       = var.environment_name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = var.log_analytics_workspace_id
  tags                       = var.tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    minimum_count         = 0
    maximum_count         = 0
  }
}

# User-assigned identities exist before the apps, so AcrPull is granted before the first image pull.
resource "azurerm_user_assigned_identity" "tools" {
  name                = "id-care-tools-backend"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "tools_acr_pull" {
  scope                            = azurerm_container_registry.this.id
  role_definition_id               = "${data.azurerm_subscription.current.id}/providers/Microsoft.Authorization/roleDefinitions/${local.acr_pull_role}"
  principal_id                     = azurerm_user_assigned_identity.tools.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "terraform_data" "build_tools" {
  count            = var.build_images ? 1 : 0
  triggers_replace = [local.tools_image]

  provisioner "local-exec" {
    working_dir = local.sources.tools
    command     = "az acr build --registry ${azurerm_container_registry.this.name} --image care-tools-backend:${local.source_hash.tools} --file Dockerfile ."
  }
  # Building takes 1-3 minutes, which also gives the AcrPull assignment time to propagate.
  depends_on = [azurerm_role_assignment.tools_acr_pull]
}

resource "azurerm_container_app" "tools" {
  name                         = "care-tools-backend"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.tools.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.tools.id
  }

  secret {
    name  = "backend-shared-secret"
    value = var.backend_shared_secret
  }

  ingress {
    # External so APIM (public, not VNet-injected) can reach it; the shared-secret header blocks direct use.
    external_enabled = true
    target_port      = 8000
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # Exactly one replica: bookings live in memory (per participant) and must not diverge.
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "api"
      image  = local.tools_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "BACKEND_SHARED_SECRET"
        secret_name = "backend-shared-secret"
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/healthz"
      }
    }
  }

  depends_on = [terraform_data.build_tools]
}

# ---- FALLBACK: A2A adapter (a2a_mode = "adapter") ----------------------------------------------
resource "azurerm_user_assigned_identity" "adapter" {
  count               = var.enable_a2a_adapter ? 1 : 0
  name                = "id-care-knowledge-a2a"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "adapter_acr_pull" {
  count                            = var.enable_a2a_adapter ? 1 : 0
  scope                            = azurerm_container_registry.this.id
  role_definition_id               = "${data.azurerm_subscription.current.id}/providers/Microsoft.Authorization/roleDefinitions/${local.acr_pull_role}"
  principal_id                     = azurerm_user_assigned_identity.adapter[0].principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

# The adapter invokes the Foundry prompt agent (responses API) with its own identity.
resource "azurerm_role_assignment" "adapter_foundry_user" {
  count                            = var.enable_a2a_adapter ? 1 : 0
  scope                            = var.foundry_project_id
  role_definition_id               = "${data.azurerm_subscription.current.id}/providers/Microsoft.Authorization/roleDefinitions/${local.foundry_user}"
  principal_id                     = azurerm_user_assigned_identity.adapter[0].principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "terraform_data" "build_adapter" {
  count            = var.enable_a2a_adapter && var.build_images ? 1 : 0
  triggers_replace = [local.adapter_image]

  provisioner "local-exec" {
    working_dir = local.sources.adapter
    command     = "az acr build --registry ${azurerm_container_registry.this.name} --image care-knowledge-a2a:${local.source_hash.adapter} --file Dockerfile ."
  }
  depends_on = [azurerm_role_assignment.adapter_acr_pull]
}

resource "azurerm_container_app" "adapter" {
  count                        = var.enable_a2a_adapter ? 1 : 0
  name                         = "care-knowledge-a2a"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.adapter[0].id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.adapter[0].id
  }

  secret {
    name  = "backend-shared-secret"
    value = var.backend_shared_secret
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "adapter"
      image  = local.adapter_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "BACKEND_SHARED_SECRET"
        secret_name = "backend-shared-secret"
      }
      env {
        name  = "FOUNDRY_PROJECT_ENDPOINT"
        value = var.foundry_project_endpoint
      }
      env {
        name  = "FOUNDRY_AGENT_NAME"
        value = "care-knowledge-agent"
      }
      env {
        name  = "PUBLIC_A2A_URL"
        value = var.public_a2a_url
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.adapter[0].client_id
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8080
        path      = "/healthz"
      }
    }
  }

  depends_on = [terraform_data.build_adapter, azurerm_role_assignment.adapter_foundry_user]
}
