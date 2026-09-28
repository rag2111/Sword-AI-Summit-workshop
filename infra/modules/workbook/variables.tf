variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "app_insights_id" {
  type = string
}

variable "display_name" {
  type = string
}

variable "tags" {
  type = map(string)
}
