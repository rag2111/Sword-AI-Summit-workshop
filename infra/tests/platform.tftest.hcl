# Terraform native tests (Terraform >= 1.9): `terraform init -backend=false && terraform test`
# Uses mock providers only, so no Azure credentials are needed and nothing is deployed.
# Post-deploy scripts and image builds are disabled with run_post_deploy = false.

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      object_id       = "11111111-1111-1111-1111-111111111111"
      tenant_id       = "22222222-2222-2222-2222-222222222222"
      subscription_id = "00000000-0000-0000-0000-000000000000"
    }
  }
  mock_data "azurerm_subscription" {
    defaults = {
      id              = "/subscriptions/00000000-0000-0000-0000-000000000000"
      subscription_id = "00000000-0000-0000-0000-000000000000"
    }
  }
  mock_resource "azurerm_application_insights" {
    defaults = {
      id                  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Insights/components/appi"
      instrumentation_key = "33333333-3333-3333-3333-333333333333"
      connection_string   = "InstrumentationKey=33333333-3333-3333-3333-333333333333;IngestionEndpoint=https://swedencentral-0.in.applicationinsights.azure.com/;LiveEndpoint=https://swedencentral.livediagnostics.monitor.azure.com/"
    }
  }
}

mock_provider "azapi" {
  mock_resource "azapi_resource" {
    defaults = {
      output = {
        properties = {
          gatewayUrl       = "https://carews-apim-mock.azure-api.net"
          primaryEndpoints = { blob = "https://stcarewsmock.blob.core.windows.net/" }
        }
      }
    }
  }
}

mock_provider "local" {}

variables {
  publisher_email   = "workshop-admin@example.com"
  participant_count = 3
  run_post_deploy   = false
}

run "default_platform" {
  command = apply

  assert {
    condition     = length(output.participant_names) == 3
    error_message = "One subscription per participant expected."
  }
  assert {
    condition     = alltrue([for n in output.participant_names : can(regex("^user[0-9]{2}$", n))])
    error_message = "Participant names must match user<2 digits>."
  }
  assert {
    condition     = output.participant_routes.mcp == "https://carews-apim-mock.azure-api.net/care-tools/mcp"
    error_message = "MCP route must be <APIM>/care-tools/mcp."
  }
  assert {
    condition     = output.participant_routes.a2a_agent_card == "https://carews-apim-mock.azure-api.net/a2a/care-knowledge/.well-known/agent-card.json"
    error_message = "Agent card route must follow the contract."
  }
  assert {
    condition     = output.foundry_project_name == "carews-proj"
    error_message = "Foundry project must be named <prefix>-proj."
  }
  assert {
    condition     = length(module.apim_apis.mcp_tool_names) == 7
    error_message = "The MCP server must expose exactly 7 tools."
  }
  assert {
    condition     = output.models.chat == "gpt-6-luna" && output.models.judge == "gpt-6-sol"
    error_message = "Default chat/judge models must follow the contract."
  }
}

run "adapter_fallback_with_http_api" {
  command = plan

  variables {
    a2a_mode                           = "adapter"
    a2a_apim_api_kind                  = "http"
    telemetry_require_subscription_key = false
    enable_content_safety              = true
    base_agent_model_route             = "direct"
  }

  assert {
    condition     = output.a2a.mode == "adapter" && output.a2a.api_kind == "http"
    error_message = "Fallback A2A wiring should be selectable."
  }
}

run "rejects_consumption_tier" {
  command = plan

  variables {
    apim_sku = "Consumption"
  }
  expect_failures = [var.apim_sku]
}
