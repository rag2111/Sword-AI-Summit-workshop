output "id" {
  value = azurerm_application_insights_workbook.this.id
}

output "portal_url" {
  value = "https://portal.azure.com/#resource${azurerm_application_insights_workbook.this.id}/workbook"
}
