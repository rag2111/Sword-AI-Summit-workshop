variable "apim_id" {
  type = string
}

variable "apim_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "gateway_url" {
  type = string
}

variable "product_id" {
  type = string
}

variable "shared_secret_nv" {
  description = "Name of the APIM named value holding the backend shared secret (also used as an ordering dependency)."
  type        = string
}

variable "appinsights_logger_id" {
  type = string
}

variable "foundry_account_name" {
  type = string
}

variable "foundry_project_name" {
  type = string
}

variable "chat_model" {
  type = string
}

variable "judge_model" {
  type = string
}

variable "token_limit_tpm" {
  type = number
}

variable "enable_content_safety" {
  type = bool
}

variable "care_tools_fqdn" {
  type = string
}

variable "care_tools_openapi_path" {
  type = string
}

variable "care_tools_rest_in_product" {
  type = bool
}

variable "a2a_mode" {
  type = string
}

variable "a2a_api_kind" {
  type = string
}

variable "a2a_adapter_url" {
  type     = string
  default  = null
  nullable = true
}

variable "telemetry_ingestion_endpoint" {
  type      = string
  sensitive = true
}

variable "telemetry_instrumentation_key" {
  type      = string
  sensitive = true
}

variable "telemetry_require_subscription_key" {
  type = bool
}

variable "backends" {
  description = "APIM backend entity names: openai, project, content_safety."
  type        = map(string)
}
