# One APIM subscription per participant in the workshop-participants product.
# Name = "user" + 2 digits; primary key = name + 3 random lowercase alphanumerics (CONTRACT §1).
# Keys are only written to git-ignored files under infra/out/ and to a sensitive output.

resource "random_password" "key_suffix" {
  count   = var.participant_count
  length  = 3
  lower   = true
  upper   = false
  numeric = true
  special = false
}

locals {
  names = [for i in range(var.participant_count) : format("user%02d", i + 1)]
}

resource "azurerm_api_management_subscription" "participant" {
  count               = var.participant_count
  api_management_name = var.apim_name
  resource_group_name = var.resource_group_name
  product_id          = var.product_id
  # becomes context.Subscription.Id
  subscription_id = local.names[count.index]
  # becomes context.Subscription.Name ("User ID" dimension)
  display_name  = local.names[count.index]
  primary_key   = "${local.names[count.index]}${random_password.key_suffix[count.index].result}"
  state         = "active"
  allow_tracing = false
}

locals {
  base = var.env_values["APIM_BASE_URL"]
  env_files = [
    for i, name in local.names : templatefile("${path.module}/participant.env.tftpl", {
      apim_base_url       = local.base
      subscription_key    = azurerm_api_management_subscription.participant[i].primary_key
      participant_id      = name
      openai_api_version  = var.env_values["OPENAI_API_VERSION"]
      chat_model          = var.env_values["CHAT_MODEL"]
      judge_model         = var.env_values["JUDGE_MODEL"]
      embedding_model     = var.env_values["EMBEDDING_MODEL"]
      project_name        = var.env_values["FOUNDRY_PROJECT_NAME"]
      instrumentation_key = var.env_values["INSTRUMENTATION_KEY"]
    })
  ]
}

resource "local_sensitive_file" "env" {
  count           = var.participant_count
  filename        = "${var.output_dir}/participants/${local.names[count.index]}.env"
  content         = local.env_files[count.index]
  file_permission = "0600"
}

resource "local_sensitive_file" "csv" {
  filename = "${var.output_dir}/participants.csv"
  content = join("", concat(["name,key,env_file\n"], [
    for i, name in local.names : "${name},${azurerm_api_management_subscription.participant[i].primary_key},out/participants/${name}.env\n"
  ]))
  file_permission = "0600"
}
