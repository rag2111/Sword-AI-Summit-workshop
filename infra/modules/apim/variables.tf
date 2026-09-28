variable "resource_group_id" {
  type = string
}

variable "location" {
  type = string
}

variable "name" {
  type = string
}

variable "sku" {
  type = string
}

variable "capacity" {
  type = number
}

variable "publisher_name" {
  type = string
}

variable "publisher_email" {
  type = string
}

variable "app_insights_id" {
  type = string
}

variable "app_insights_connection_string" {
  type      = string
  sensitive = true
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "backend_shared_secret" {
  type      = string
  sensitive = true
}

variable "foundry_account_name" {
  type = string
}

variable "enable_content_safety" {
  type = bool
}

variable "tags" {
  type = map(string)
}
