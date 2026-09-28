output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "apim_gateway_url" {
  description = "APIM_BASE_URL for participants."
  value       = module.apim.gateway_url
}

output "apim_name" {
  value = module.apim.name
}

output "participant_routes" {
  description = "Participant-facing routes (CONTRACT §2)."
  value = {
    openai          = "${module.apim.gateway_url}/openai"
    mcp             = "${module.apim.gateway_url}/care-tools/mcp"
    a2a             = "${module.apim.gateway_url}/a2a/care-knowledge"
    a2a_agent_card  = "${module.apim.gateway_url}/a2a/care-knowledge/.well-known/agent-card.json"
    foundry_project = "${module.apim.gateway_url}/foundry/api/projects/${module.foundry.project_name}"
    telemetry       = "${module.apim.gateway_url}/telemetry/"
    config          = "${module.apim.gateway_url}/telemetry/config"
  }
}

output "participant_names" {
  description = "Subscription/participant names (not secret)."
  value       = module.participants.names
}

output "participant_keys" {
  description = "Map participant name -> primary APIM subscription key. Read with: terraform output -json participant_keys"
  value       = module.participants.keys
  sensitive   = true
}

output "participants_csv" {
  description = "Git-ignored CSV (name,key,env_file) for handing out keys."
  value       = module.participants.csv_path
}

output "participant_env_dir" {
  description = "Git-ignored directory with one .env file per participant."
  value       = module.participants.env_dir
}

output "foundry_project_name" {
  value = module.foundry.project_name
}

output "foundry_project_endpoint_direct" {
  description = "ADMIN ONLY. Participants use the APIM /foundry route instead."
  value       = module.foundry.project_endpoint
}

output "models" {
  value = { chat = local.chat_model, judge = local.judge_model, embedding = local.embed_model }
}

output "application_insights_connection_string" {
  description = "Direct App Insights connection string (admin/presenter). Participants get the APIM-ingestion variant."
  value       = module.monitoring.connection_string
  sensitive   = true
}

output "workbook_url" {
  value = module.workbook.portal_url
}

output "a2a" {
  value = {
    mode     = var.a2a_mode
    api_kind = var.a2a_apim_api_kind
    adapter  = module.container_apps.a2a_adapter_url
  }
}

output "base_agent_info_file" {
  description = "Written by scripts/create_base_agent.py (agent version, model route, grounding mode)."
  value       = "${path.module}/out/base_agent.json"
}
