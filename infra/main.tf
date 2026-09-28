# Care Coordination workshop — base platform (Deliverable 1).
# Read top to bottom: names -> monitoring -> knowledge storage/search -> Foundry -> container apps ->
# APIM (service, APIs, participants) -> RBAC (rbac.tf) -> post-deploy scripts (post_deploy.tf).

data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
  numeric = true
}

# Shared secret that only APIM (named value) and the Container Apps know: blocks gateway bypass.
resource "random_password" "backend_secret" {
  length  = 40
  special = false
}

locals {
  suffix         = random_string.suffix.result
  compact_prefix = replace(var.prefix, "-", "")

  names = {
    resource_group = "rg-${var.prefix}-${local.suffix}"
    foundry        = "${var.prefix}-foundry-${local.suffix}"
    project        = "${var.prefix}-proj"
    apim           = "${var.prefix}-apim-${local.suffix}"
    search         = "${var.prefix}-search-${local.suffix}"
    storage        = substr("st${local.compact_prefix}${local.suffix}", 0, 24)
    registry       = substr("acr${local.compact_prefix}${local.suffix}", 0, 50)
    log_analytics  = "${var.prefix}-law-${local.suffix}"
    app_insights   = "${var.prefix}-appi-${local.suffix}"
    container_env  = "${var.prefix}-cae-${local.suffix}"
  }

  # The gateway hostname is deterministic, so apps and .env files can reference it before APIM exists.
  apim_gateway_url = "https://${local.names.apim}.azure-api.net"

  deployments = { for d in var.model_deployments : d.role => d }
  chat_model  = local.deployments["chat"].name
  judge_model = local.deployments["judge"].name
  embed_model = local.deployments["embedding"].name

  tags = merge(var.tags, { "workshop-prefix" = var.prefix })
}

resource "azurerm_resource_group" "this" {
  name     = local.names.resource_group
  location = var.location
  tags     = local.tags
}

module "monitoring" {
  source              = "./modules/monitoring"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  log_analytics_name  = local.names.log_analytics
  app_insights_name   = local.names.app_insights
  tags                = local.tags
}

module "search_storage" {
  source                   = "./modules/search_storage"
  resource_group_id        = azurerm_resource_group.this.id
  location                 = var.location
  storage_account_name     = local.names.storage
  search_service_name      = local.names.search
  search_sku               = var.search_sku
  knowledge_retrieval_plan = var.search_knowledge_retrieval_plan
  docs_container_name      = "care-docs"
  tags                     = local.tags
}

module "foundry" {
  source            = "./modules/foundry"
  resource_group_id = azurerm_resource_group.this.id
  location          = var.location
  account_name      = local.names.foundry
  project_name      = local.names.project
  model_deployments = var.model_deployments
  tags              = local.tags

  app_insights_id                = module.monitoring.app_insights_id
  app_insights_connection_string = module.monitoring.connection_string
  search_service_id              = module.search_storage.search_service_id
  search_endpoint                = module.search_storage.search_endpoint
  storage_account_id             = module.search_storage.storage_account_id
  storage_blob_endpoint          = module.search_storage.blob_endpoint
}

module "container_apps" {
  source                     = "./modules/container_apps"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = var.location
  registry_name              = local.names.registry
  environment_name           = local.names.container_env
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  backend_shared_secret      = random_password.backend_secret.result
  build_images               = var.run_post_deploy
  tags                       = local.tags

  enable_a2a_adapter       = var.a2a_mode == "adapter"
  public_a2a_url           = "${local.apim_gateway_url}/a2a/care-knowledge"
  foundry_project_endpoint = module.foundry.project_endpoint
  foundry_project_id       = module.foundry.project_id
}

module "apim" {
  source            = "./modules/apim"
  resource_group_id = azurerm_resource_group.this.id
  location          = var.location
  name              = local.names.apim
  sku               = var.apim_sku
  capacity          = var.apim_capacity
  publisher_name    = var.publisher_name
  publisher_email   = var.publisher_email
  tags              = local.tags

  app_insights_id                = module.monitoring.app_insights_id
  app_insights_connection_string = module.monitoring.connection_string
  log_analytics_workspace_id     = module.monitoring.log_analytics_workspace_id
  backend_shared_secret          = random_password.backend_secret.result
  foundry_account_name           = module.foundry.account_name
  enable_content_safety          = var.enable_content_safety
}

module "apim_apis" {
  source              = "./modules/apim_apis"
  apim_id             = module.apim.id
  apim_name           = module.apim.name
  resource_group_name = azurerm_resource_group.this.name
  gateway_url         = module.apim.gateway_url
  product_id          = module.apim.product_id
  shared_secret_nv    = module.apim.backend_secret_named_value

  appinsights_logger_id = module.apim.appinsights_logger_id
  backends              = module.apim.backends

  foundry_account_name  = module.foundry.account_name
  foundry_project_name  = module.foundry.project_name
  chat_model            = local.chat_model
  judge_model           = local.judge_model
  token_limit_tpm       = var.token_limit_tpm
  enable_content_safety = var.enable_content_safety

  care_tools_fqdn            = module.container_apps.care_tools_fqdn
  care_tools_openapi_path    = "${path.module}/apps/care_tools_backend/app/openapi.json"
  care_tools_rest_in_product = var.care_tools_rest_in_product

  a2a_mode        = var.a2a_mode
  a2a_api_kind    = var.a2a_apim_api_kind
  a2a_adapter_url = module.container_apps.a2a_adapter_url

  telemetry_ingestion_endpoint       = module.monitoring.ingestion_endpoint
  telemetry_instrumentation_key      = module.monitoring.instrumentation_key
  telemetry_require_subscription_key = var.telemetry_require_subscription_key
}

module "participants" {
  source              = "./modules/participants"
  participant_count   = var.participant_count
  apim_name           = module.apim.name
  resource_group_name = azurerm_resource_group.this.name
  product_id          = module.apim.product_id
  output_dir          = "${path.module}/out"

  env_values = {
    APIM_BASE_URL        = module.apim.gateway_url
    OPENAI_API_VERSION   = var.openai_api_version
    CHAT_MODEL           = local.chat_model
    JUDGE_MODEL          = local.judge_model
    EMBEDDING_MODEL      = local.embed_model
    FOUNDRY_PROJECT_NAME = module.foundry.project_name
    INSTRUMENTATION_KEY  = module.monitoring.instrumentation_key
  }
  depends_on = [module.apim_apis]
}

# Dedicated APIM subscription used by Foundry Agent Service (AI-gateway connection) so the base
# agent's model traffic is metered and limited like any participant's ("User ID" = svc-foundry-agent).
resource "azurerm_api_management_subscription" "agent_service" {
  api_management_name = module.apim.name
  resource_group_name = azurerm_resource_group.this.name
  subscription_id     = "svc-foundry-agent"
  display_name        = "svc-foundry-agent"
  product_id          = module.apim.product_id
  state               = "active"
  allow_tracing       = false
}

# PREVIEW: Foundry "bring your own AI gateway" connection (category ApiManagement). Prompt agents then
# reference models as "<connection>/<deployment>" and all their model calls flow through APIM /openai.
# Fallback (documented in docs/apim-exceptions/infra.md): base_agent_model_route = "direct".
resource "azapi_resource" "apim_gateway_connection" {
  count     = var.base_agent_model_route == "direct" ? 0 : 1
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-07-15-preview"
  name      = "apim-gateway"
  parent_id = module.foundry.project_id

  body = {
    properties = {
      category      = "ApiManagement"
      target        = "${module.apim.gateway_url}/openai"
      authType      = "ApiKey"
      isSharedToAll = true
      metadata = {
        deploymentInPath    = "true"
        inferenceAPIVersion = var.openai_api_version
        models = jsonencode([
          for d in var.model_deployments : {
            name       = d.name
            properties = { model = { name = d.model, version = d.version, format = "OpenAI" } }
          } if d.role != "embedding"
        ])
      }
    }
  }
  sensitive_body = {
    properties = { credentials = { key = azurerm_api_management_subscription.agent_service.primary_key } }
  }
  schema_validation_enabled = false
  depends_on                = [module.apim_apis]
}

module "workbook" {
  source              = "./modules/workbook"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  app_insights_id     = module.monitoring.app_insights_id
  display_name        = "Sword AI Summit workshop - participant usage"
  tags                = local.tags
}
