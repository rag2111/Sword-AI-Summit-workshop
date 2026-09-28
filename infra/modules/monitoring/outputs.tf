output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.this.id
}

output "app_insights_id" {
  value = azurerm_application_insights.this.id
}

output "connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}

output "instrumentation_key" {
  value     = azurerm_application_insights.this.instrumentation_key
  sensitive = true
}

output "ingestion_endpoint" {
  description = "Regional ingestion endpoint without trailing slash, e.g. https://swedencentral-0.in.applicationinsights.azure.com"
  value       = local.ingestion_endpoint
  sensitive   = true
}
