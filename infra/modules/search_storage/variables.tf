variable "resource_group_id" {
  type = string
}

variable "location" {
  type = string
}

variable "storage_account_name" {
  type = string
}

variable "search_service_name" {
  type = string
}

variable "search_sku" {
  type = string
}

variable "knowledge_retrieval_plan" {
  type = string
}

variable "docs_container_name" {
  type = string
}

variable "tags" {
  type = map(string)
}
