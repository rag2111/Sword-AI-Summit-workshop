variable "resource_group_id" {
  type = string
}

variable "location" {
  type = string
}

variable "account_name" {
  type = string
}

variable "project_name" {
  type = string
}

variable "model_deployments" {
  type = list(object({
    name     = string
    model    = string
    version  = string
    sku      = string
    capacity = number
    role     = string
  }))
}

variable "app_insights_id" {
  type = string
}

variable "app_insights_connection_string" {
  type      = string
  sensitive = true
}

variable "search_service_id" {
  type = string
}

variable "search_endpoint" {
  type = string
}

variable "storage_account_id" {
  type = string
}

variable "storage_blob_endpoint" {
  type = string
}

variable "tags" {
  type = map(string)
}
