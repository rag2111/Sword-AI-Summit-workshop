# Least-privilege role assignments. Role definition IDs are used instead of names because Foundry
# roles were renamed (Azure AI User -> Foundry User); the IDs did not change.
locals {
  role = {
    cognitive_services_openai_user = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"
    cognitive_services_user        = "a97b65f3-24c7-4388-baec-2e87135dc908"
    foundry_user                   = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
    search_index_data_reader       = "1407120a-92aa-4202-b7e9-c0e197c71c8f"
    search_index_data_contributor  = "8ebe5a00-799e-43f5-93ac-243d3dce84a7"
    search_service_contributor     = "7ca78c08-252a-4471-8644-bb5ff32d4ba0"
    storage_blob_data_reader       = "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"
    storage_blob_data_contributor  = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
  }

  deployer = data.azurerm_client_config.current.object_id

  role_assignments = merge(
    {
      # APIM managed identity: model calls on /openai ...
      apim_openai_user = { scope = module.foundry.account_id, role = "cognitive_services_openai_user", principal = module.apim.principal_id, service = true }
      # ... and Foundry project data plane (/foundry proxy) + incoming A2A (/a2a/care-knowledge).
      apim_foundry_user = { scope = module.foundry.project_id, role = "foundry_user", principal = module.apim.principal_id, service = true }

      # Azure AI Search managed identity: read the blob container, call embedding/chat models for Foundry IQ.
      search_blob_reader = { scope = module.search_storage.storage_account_id, role = "storage_blob_data_reader", principal = module.search_storage.search_principal_id, service = true }
      search_models      = { scope = module.foundry.account_id, role = "cognitive_services_user", principal = module.search_storage.search_principal_id, service = true }

      # Foundry project managed identity: agent tools read the search index / knowledge base; cloud evals call the judge model.
      project_search_reader = { scope = module.search_storage.search_service_id, role = "search_index_data_reader", principal = module.foundry.project_principal_id, service = true }
      project_openai_user   = { scope = module.foundry.account_id, role = "cognitive_services_openai_user", principal = module.foundry.project_principal_id, service = true }

      # The admin running Terraform: post-deploy scripts (upload docs, create index/KB, create the base agent).
      deployer_blob_contributor   = { scope = module.search_storage.storage_account_id, role = "storage_blob_data_contributor", principal = local.deployer, service = false }
      deployer_search_contributor = { scope = module.search_storage.search_service_id, role = "search_service_contributor", principal = local.deployer, service = false }
      deployer_search_data        = { scope = module.search_storage.search_service_id, role = "search_index_data_contributor", principal = local.deployer, service = false }
      deployer_foundry_user       = { scope = module.foundry.project_id, role = "foundry_user", principal = local.deployer, service = false }
    },
    var.enable_content_safety ? {
      # llm-content-safety calls the Foundry resource's Content Safety endpoint with APIM's identity.
      apim_content_safety = { scope = module.foundry.account_id, role = "cognitive_services_user", principal = module.apim.principal_id, service = true }
    } : {}
  )
}

resource "azurerm_role_assignment" "this" {
  for_each = local.role_assignments

  scope              = each.value.scope
  role_definition_id = "${data.azurerm_subscription.current.id}/providers/Microsoft.Authorization/roleDefinitions/${local.role[each.value.role]}"
  principal_id       = each.value.principal
  # Managed identities are ServicePrincipals; setting the type avoids Entra replication-delay errors.
  principal_type                   = each.value.service ? "ServicePrincipal" : null
  skip_service_principal_aad_check = each.value.service
}
