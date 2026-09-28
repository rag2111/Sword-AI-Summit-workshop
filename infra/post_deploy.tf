# Post-deploy steps that have no ARM resource: they call data-plane APIs (Search, Foundry Agent
# Service). Each script is idempotent and re-runs only when its inputs change (triggers_replace).
# Requires `uv` and a logged-in Azure CLI on the machine running Terraform.

locals {
  docs_hash        = sha1(join("", [for f in sort(fileset("${path.module}/data/care-docs", "*.md")) : filesha1("${path.module}/data/care-docs/${f}")]))
  base_agent_model = coalesce(var.base_agent_model_deployment, local.chat_model)
}

resource "terraform_data" "seed_knowledge" {
  count = var.run_post_deploy ? 1 : 0

  triggers_replace = {
    docs           = local.docs_hash
    script         = filesha1("${path.module}/scripts/seed_knowledge.py")
    search_service = module.search_storage.search_service_id
    mode           = var.knowledge_mode
    models         = "${local.chat_model}|${local.embed_model}"
  }

  provisioner "local-exec" {
    working_dir = path.module
    command     = "uv run scripts/seed_knowledge.py"
    environment = {
      STORAGE_BLOB_ENDPOINT   = module.search_storage.blob_endpoint
      STORAGE_ACCOUNT_ID      = module.search_storage.storage_account_id
      DOCS_CONTAINER          = module.search_storage.docs_container_name
      SEARCH_ENDPOINT         = module.search_storage.search_endpoint
      FOUNDRY_OPENAI_ENDPOINT = module.foundry.openai_endpoint
      CHAT_DEPLOYMENT         = local.chat_model
      CHAT_MODEL              = local.deployments["chat"].model
      EMBEDDING_DEPLOYMENT    = local.embed_model
      EMBEDDING_MODEL         = local.deployments["embedding"].model
      KNOWLEDGE_MODE          = var.knowledge_mode
    }
  }

  depends_on = [azurerm_role_assignment.this, module.foundry]
}

resource "terraform_data" "base_agent" {
  count = var.run_post_deploy ? 1 : 0

  triggers_replace = {
    knowledge   = terraform_data.seed_knowledge[0].id
    script      = filesha1("${path.module}/scripts/create_base_agent.py")
    model_route = var.base_agent_model_route
    chat        = local.base_agent_model
    a2a_mode    = var.a2a_mode
    gateway     = try(azapi_resource.apim_gateway_connection[0].id, "none")
  }

  provisioner "local-exec" {
    working_dir = path.module
    command     = "uv run scripts/create_base_agent.py"
    environment = {
      FOUNDRY_PROJECT_ENDPOINT    = module.foundry.project_endpoint
      FOUNDRY_PROJECT_RESOURCE_ID = module.foundry.project_id
      SEARCH_CONNECTION_NAME      = module.foundry.search_connection_name
      CHAT_DEPLOYMENT             = local.base_agent_model
      MODEL_ROUTE                 = var.base_agent_model_route
      APIM_CONNECTION_NAME        = try(azapi_resource.apim_gateway_connection[0].name, "")
      # Incoming A2A (preview) is only needed when APIM talks to Foundry's native A2A endpoint.
      ENABLE_A2A = var.a2a_mode == "native_foundry" ? "true" : "false"
    }
  }

  depends_on = [module.apim_apis, azapi_resource.apim_gateway_connection, azurerm_role_assignment.this]
}
