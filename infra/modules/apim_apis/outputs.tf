output "api_ids" {
  value = {
    openai         = azapi_resource.openai.id
    care_tools_api = azapi_resource.care_tools_api.id
    care_tools_mcp = azapi_resource.care_tools_mcp.id
    a2a            = local.a2a_api_id
    foundry        = azapi_resource.foundry.id
    telemetry      = azapi_resource.telemetry.id
  }
}

output "mcp_tool_names" {
  value = sort(keys(local.tools))
}
