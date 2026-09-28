# Azure Monitor workbook over the workshop Application Insights resource: per-participant token usage
# (custom metrics from llm-emit-token-metric), latency and errors per route, MCP tool calls, A2A calls.
resource "random_uuid" "workbook" {}

resource "azurerm_application_insights_workbook" "this" {
  name                = random_uuid.workbook.result
  resource_group_name = var.resource_group_name
  location            = var.location
  display_name        = var.display_name
  source_id           = lower(var.app_insights_id)
  category            = "workbook"
  data_json           = file("${path.module}/workbook.json")
  tags                = var.tags
}
