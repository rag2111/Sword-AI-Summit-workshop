# Real random provider, mocked Azure/filesystem: validate keys without creating subscriptions or files.
mock_provider "azurerm" {}
mock_provider "local" {}

variables {
  participant_count   = 3
  apim_name           = "apim-test"
  resource_group_name = "rg-test"
  product_id          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ApiManagement/service/apim-test/products/workshop-participants"
  output_dir          = "./out"
  env_values = {
    APIM_BASE_URL        = "https://apim-test.azure-api.net"
    OPENAI_API_VERSION   = "2024-10-21"
    CHAT_MODEL           = "gpt-6-luna"
    JUDGE_MODEL          = "gpt-6-sol"
    EMBEDDING_MODEL      = "text-embedding-3-large"
    FOUNDRY_PROJECT_NAME = "test-proj"
    INSTRUMENTATION_KEY  = "11111111-1111-1111-1111-111111111111"
  }
}

run "participant_credentials" {
  command = apply

  module {
    source = "./modules/participants"
  }

  assert {
    condition     = output.names == ["user01", "user02", "user03"]
    error_message = "Names must be user + two-digit number, without the key suffix."
  }
  assert {
    condition     = alltrue([for name, key in output.keys : can(regex("^${name}[a-z0-9]{3}$", key))])
    error_message = "Primary keys must be the participant name plus exactly three lowercase alphanumerics."
  }
  assert {
    condition     = alltrue([for i, sub in azurerm_api_management_subscription.participant : sub.subscription_id == output.names[i] && sub.display_name == output.names[i]])
    error_message = "Subscription IDs and display names must both use the participant name."
  }
  assert {
    condition     = alltrue([for i, env in local_sensitive_file.env : env.filename == "./out/participants/${output.names[i]}.env" && strcontains(env.content, "PARTICIPANT_ID=${output.names[i]}\n") && strcontains(env.content, "APIM_SUBSCRIPTION_KEY=${output.keys[output.names[i]]}\n")])
    error_message = "Each environment file must contain its matching username and actual primary key."
  }
  assert {
    condition     = local_sensitive_file.csv.content == join("", concat(["name,key,env_file\n"], [for name in output.names : "${name},${output.keys[name]},out/participants/${name}.env\n"]))
    error_message = "CSV must use the same names and keys as the subscription and environment exports."
  }
}

run "keys_stable_on_replan" {
  command = plan

  module {
    source = "./modules/participants"
  }

  assert {
    condition     = output.keys == run.participant_credentials.keys
    error_message = "A repeated plan must not rotate participant primary keys."
  }
}

run "supports_all_two_digit_numbers" {
  command = apply

  module {
    source = "./modules/participants"
  }

  variables {
    participant_count = 99
  }

  assert {
    condition     = output.names[0] == "user01" && output.names[98] == "user99" && length(distinct(output.names)) == 99
    error_message = "Names must stay unique across the supported range 01..99."
  }
  assert {
    condition     = length(distinct(values(output.keys))) == 99 && alltrue([for name, key in output.keys : can(regex("^${name}[a-z0-9]{3}$", key))])
    error_message = "Every primary key must remain unique and match the exact format through user99."
  }
  assert {
    condition     = alltrue([for name, key in run.participant_credentials.keys : output.keys[name] == key])
    error_message = "Adding participants must not rotate existing keys."
  }
}
