# Log Analytics + workspace-based Application Insights: the single trace store for the workshop
# (participants' agents via APIM /telemetry, APIM request spans, Foundry tracing via the project connection).
resource "azurerm_log_analytics_workspace" "this" {
  name                = var.log_analytics_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = var.app_insights_name
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  retention_in_days   = 30
  # Local (iKey) auth stays enabled: the APIM /telemetry proxy forwards iKey-authenticated envelopes.
  tags = var.tags
}

locals {
  # "InstrumentationKey=...;IngestionEndpoint=https://<region>.in.applicationinsights.azure.com/;..."
  # Derived from the (sensitive) connection string, so Terraform keeps it marked sensitive.
  cs_parts           = { for p in split(";", azurerm_application_insights.this.connection_string) : split("=", p)[0] => join("=", slice(split("=", p), 1, length(split("=", p)))) if length(split("=", p)) > 1 }
  ingestion_endpoint = trimsuffix(local.cs_parts["IngestionEndpoint"], "/")
}
