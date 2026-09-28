output "id" {
  value = azapi_resource.service.id
}

output "name" {
  value = azapi_resource.service.name
}

output "gateway_url" {
  value = azapi_resource.service.output.properties.gatewayUrl
}

output "principal_id" {
  value = azapi_resource.service.identity[0].principal_id
}

output "product_id" {
  description = "ARM ID of the workshop-participants product."
  value       = azapi_resource.product.id
}

output "backend_secret_named_value" {
  value = azapi_resource.nv_backend_secret.name
}

output "appinsights_logger_id" {
  value = azapi_resource.logger_appinsights.id
}

output "backends" {
  description = "Backend entity names (referenced by API policies, which also orders creation)."
  value = {
    openai         = azapi_resource.backend_openai.name
    project        = azapi_resource.backend_project.name
    content_safety = try(azapi_resource.backend_content_safety[0].name, "")
  }
}
