variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "registry_name" {
  type = string
}

variable "environment_name" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "backend_shared_secret" {
  type      = string
  sensitive = true
}

variable "build_images" {
  description = "Run `az acr build` via local-exec (false for plan-only validation)."
  type        = bool
}

variable "enable_a2a_adapter" {
  type = bool
}

variable "public_a2a_url" {
  description = "APIM URL advertised in the adapter's Agent Card."
  type        = string
}

variable "foundry_project_endpoint" {
  type = string
}

variable "foundry_project_id" {
  type = string
}

variable "tags" {
  type = map(string)
}
