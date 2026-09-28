mock_provider "azurerm" {}

mock_provider "azapi" {
  mock_resource "azapi_resource" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test"
      output = {
        properties = { gatewayUrl = "https://apim-test.azure-api.net" }
      }
    }
  }
}

run "updates_builtin_objects" {
  command = apply

  module {
    source = "./modules/apim"
  }

  variables {
    resource_group_id              = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test"
    location                       = "swedencentral"
    name                           = "apim-test"
    sku                            = "StandardV2"
    capacity                       = 1
    publisher_name                 = "Workshop"
    publisher_email                = "workshop@example.com"
    app_insights_id                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Insights/components/appi-test"
    app_insights_connection_string = "InstrumentationKey=11111111-1111-1111-1111-111111111111"
    log_analytics_workspace_id     = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.OperationalInsights/workspaces/law-test"
    backend_shared_secret          = "mock-only"
    foundry_account_name           = "foundry-test"
    enable_content_safety          = false
    tags                           = {}
  }

  assert {
    condition     = azapi_update_resource.logger_azuremonitor.name == "azuremonitor" && azapi_update_resource.logger_azuremonitor.body.properties.loggerType == "azureMonitor"
    error_message = "Configure the built-in Azure Monitor logger with an update."
  }
  assert {
    condition     = azapi_update_resource.diag_azuremonitor.body.properties.loggerId == azapi_update_resource.logger_azuremonitor.id
    error_message = "Diagnostics must reference the updated built-in logger."
  }
  assert {
    condition     = azapi_update_resource.global_policy.body.properties.value == file("./modules/apim/policies/global.xml")
    error_message = "The existing global policy must receive the workshop policy."
  }
}

run "binds_default_routes" {
  command = apply

  module {
    source = "./modules/apim_apis"
  }

  variables {
    apim_id                            = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test"
    apim_name                          = "apim-test"
    resource_group_name                = "rg-test"
    gateway_url                        = "https://apim-test.azure-api.net"
    product_id                         = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test/products/workshop-participants"
    shared_secret_nv                   = "backend-shared-secret"
    appinsights_logger_id              = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test/loggers/appinsights"
    foundry_account_name               = "foundry-test"
    foundry_project_name               = "test-proj"
    chat_model                         = "gpt-6-luna"
    judge_model                        = "gpt-6-sol"
    token_limit_tpm                    = 10000
    enable_content_safety              = false
    care_tools_fqdn                    = "tools.example.com"
    care_tools_openapi_path            = "./apps/care_tools_backend/app/openapi.json"
    care_tools_rest_in_product         = false
    a2a_mode                           = "native_foundry"
    a2a_api_kind                       = "a2a"
    telemetry_ingestion_endpoint       = "https://example.in.applicationinsights.azure.com"
    telemetry_instrumentation_key      = "11111111-1111-1111-1111-111111111111"
    telemetry_require_subscription_key = true
    backends                           = { openai = "foundry-openai", project = "foundry-project", content_safety = "" }
  }

  assert {
    condition     = toset([for binding in azurerm_api_management_product_api.product_api : binding.api_name]) == toset(["openai", "care-tools", "care-knowledge-a2a", "foundry", "telemetry"])
    error_message = "Exactly the five participant routes must be bound using AzureRM."
  }
  assert {
    condition     = alltrue([for binding in azurerm_api_management_product_api.product_api : binding.product_id == "workshop-participants" && binding.api_management_name == "apim-test" && binding.resource_group_name == "rg-test"])
    error_message = "AzureRM needs the product name, APIM name and resource group, not the product ARM ID."
  }
  assert {
    condition     = azapi_resource.care_tools_api.body.properties.translateRequiredQueryParameters == "query"
    error_message = "Keep required query parameters out of URL templates so MCP combines them with optional query arguments correctly."
  }
}

run "binds_optional_rest_and_http_a2a" {
  command = apply

  module {
    source = "./modules/apim_apis"
  }

  variables {
    apim_id                            = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test"
    apim_name                          = "apim-test"
    resource_group_name                = "rg-test"
    gateway_url                        = "https://apim-test.azure-api.net"
    product_id                         = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test/products/workshop-participants"
    shared_secret_nv                   = "backend-shared-secret"
    appinsights_logger_id              = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test/loggers/appinsights"
    foundry_account_name               = "foundry-test"
    foundry_project_name               = "test-proj"
    chat_model                         = "gpt-6-luna"
    judge_model                        = "gpt-6-sol"
    token_limit_tpm                    = 10000
    enable_content_safety              = false
    care_tools_fqdn                    = "tools.example.com"
    care_tools_openapi_path            = "./apps/care_tools_backend/app/openapi.json"
    care_tools_rest_in_product         = true
    a2a_mode                           = "adapter"
    a2a_api_kind                       = "http"
    a2a_adapter_url                    = "https://adapter.example.com"
    telemetry_ingestion_endpoint       = "https://example.in.applicationinsights.azure.com"
    telemetry_instrumentation_key      = "11111111-1111-1111-1111-111111111111"
    telemetry_require_subscription_key = true
    backends                           = { openai = "foundry-openai", project = "foundry-project", content_safety = "" }
  }

  assert {
    condition     = length(azurerm_api_management_product_api.product_api) == 6 && azurerm_api_management_product_api.product_api["care-tools-api"].api_name == "care-tools-api"
    error_message = "Optional backing REST access must add exactly one binding."
  }
  assert {
    condition     = azurerm_api_management_product_api.product_api["a2a"].api_name == azapi_resource.a2a_http[0].name
    error_message = "The HTTP A2A fallback must retain the same product binding."
  }
}
