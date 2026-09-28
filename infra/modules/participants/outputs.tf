output "names" {
  value = local.names
}

output "keys" {
  value     = zipmap(local.names, azurerm_api_management_subscription.participant[*].primary_key)
  sensitive = true
}

output "csv_path" {
  value = local_sensitive_file.csv.filename
}

output "env_dir" {
  value = "${var.output_dir}/participants"
}
