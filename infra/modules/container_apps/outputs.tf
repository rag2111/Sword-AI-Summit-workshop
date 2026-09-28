output "care_tools_fqdn" {
  value = azurerm_container_app.tools.ingress[0].fqdn
}

output "a2a_adapter_url" {
  description = "Adapter base URL (null unless a2a_mode = adapter)."
  value       = var.enable_a2a_adapter ? "https://${azurerm_container_app.adapter[0].ingress[0].fqdn}" : null
}

output "registry_login_server" {
  value = azurerm_container_registry.this.login_server
}
