output "account_id" {
  value = azapi_resource.account.id
}

output "account_name" {
  value = azapi_resource.account.name
}

output "account_principal_id" {
  value = azapi_resource.account.identity[0].principal_id
}

output "project_id" {
  value = azapi_resource.project.id
}

output "project_name" {
  value = azapi_resource.project.name
}

output "project_principal_id" {
  value = azapi_resource.project.identity[0].principal_id
}

output "openai_endpoint" {
  value = "https://${azapi_resource.account.name}.openai.azure.com"
}

output "services_endpoint" {
  value = "https://${azapi_resource.account.name}.services.ai.azure.com"
}

output "project_endpoint" {
  description = "Direct project endpoint (admin scripts and service-to-service only)."
  value       = "https://${azapi_resource.account.name}.services.ai.azure.com/api/projects/${azapi_resource.project.name}"
}

output "search_connection_name" {
  value = azapi_resource.conn_search.name
}

output "deployment_names" {
  value = [for d in azapi_resource.deployment : d.name]
}
