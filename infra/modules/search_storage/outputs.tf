output "storage_account_id" {
  value = azapi_resource.storage.id
}

output "blob_endpoint" {
  value = trimsuffix(azapi_resource.storage.output.properties.primaryEndpoints.blob, "/")
}

output "docs_container_name" {
  value = azapi_resource.docs_container.name
}

output "search_service_id" {
  value = azapi_resource.search.id
}

output "search_endpoint" {
  value = "https://${azapi_resource.search.name}.search.windows.net"
}

output "search_principal_id" {
  value = azapi_resource.search.identity[0].principal_id
}
