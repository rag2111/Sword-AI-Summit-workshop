variable "participant_count" {
  type = number
}

variable "apim_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "product_id" {
  description = "ARM ID of the workshop-participants product."
  type        = string
}

variable "output_dir" {
  description = "Git-ignored output directory (infra/out)."
  type        = string
}

variable "env_values" {
  description = "Shared values written into every participant .env file."
  type        = map(string)
  sensitive   = true
}
