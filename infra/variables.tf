variable "subscription_id" {
  description = "Azure subscription ID. Null = use ARM_SUBSCRIPTION_ID / the Azure CLI default subscription."
  type        = string
  default     = null
}

variable "location" {
  description = "Azure region for everything. Must offer the model deployments below, APIM v2, Azure AI Search agentic retrieval and Foundry Agent Service (see README 'Region choice')."
  type        = string
  default     = "swedencentral"
}

variable "prefix" {
  description = "Short lowercase name prefix (3-12 chars, letters/digits/hyphens, starts with a letter). Drives all resource names, e.g. the Foundry project '<prefix>-proj'."
  type        = string
  default     = "sword"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,11}$", var.prefix))
    error_message = "prefix must be 3-12 chars: lowercase letters, digits, hyphens; starting with a letter."
  }
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    workload        = "sword-ai-summit-workshop"
    environment     = "training"
    data            = "synthetic-only"
    owner           = "roberto.arocha@microsoft.com"
    SecurityControl = "Ignore"
  }
}

variable "participant_count" {
  description = "Number of participant subscriptions (user01 ... userNN)."
  type        = number
  default     = 50

  validation {
    condition     = var.participant_count >= 1 && var.participant_count <= 99 && floor(var.participant_count) == var.participant_count
    error_message = "participant_count must be an integer between 1 and 99 (names use two digits)."
  }
}

variable "model_deployments" {
  description = <<-EOT
    Foundry model deployments. Exactly one deployment per role: chat, judge, embedding.
    capacity is in thousands of tokens per minute (K TPM) and must fit your regional quota.
    Check availability first:  az cognitiveservices model list -l <location> -o table
    and quota:                 az cognitiveservices usage list -l <location> -o table
  EOT
  type = list(object({
    name     = string
    model    = string
    version  = string
    sku      = string
    capacity = number
    role     = string
  }))
  default = [
    { name = "gpt-6-luna", model = "gpt-6-luna", version = "2026-09-22", sku = "DataZoneStandard", capacity = 200, role = "chat" },
    { name = "gpt-6-sol", model = "gpt-6-sol", version = "2026-09-22", sku = "DataZoneStandard", capacity = 100, role = "judge" },
    { name = "text-embedding-3-large", model = "text-embedding-3-large", version = "1", sku = "DataZoneStandard", capacity = 150, role = "embedding" },
  ]

  validation {
    condition = alltrue([
      for r in ["chat", "judge", "embedding"] : length([for d in var.model_deployments : d if d.role == r]) == 1
    ]) && alltrue([for d in var.model_deployments : contains(["chat", "judge", "embedding"], d.role)])
    error_message = "model_deployments needs exactly one entry for each role: chat, judge, embedding."
  }
}

variable "apim_sku" {
  description = "APIM tier. MCP servers + A2A APIs + llm-* policies need Developer, Basic, BasicV2, Standard, StandardV2, Premium or PremiumV2 (NOT Consumption). StandardV2 = recommended (fast deploy, SLA); Developer = cheapest (no SLA, classic, 30-60 min deploy)."
  type        = string
  default     = "StandardV2"

  validation {
    condition     = contains(["Developer", "Basic", "BasicV2", "Standard", "StandardV2", "Premium", "PremiumV2"], var.apim_sku)
    error_message = "apim_sku must support AI gateway + MCP + A2A: Developer, Basic, BasicV2, Standard, StandardV2, Premium or PremiumV2."
  }
}

variable "apim_capacity" {
  description = "APIM scale units (1 is plenty for 30 participants)."
  type        = number
  default     = 1
}

variable "publisher_name" {
  description = "APIM publisher (organisation) name."
  type        = string
  default     = "Sword AI Summit Workshop"
}

variable "publisher_email" {
  description = "APIM publisher email (receives APIM system notifications)."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.publisher_email))
    error_message = "publisher_email must be a valid email address."
  }
}

variable "token_limit_tpm" {
  description = "Per-participant (per APIM subscription) token limit in tokens per minute, enforced by llm-token-limit on /openai."
  type        = number
  default     = 20000
}

variable "enable_content_safety" {
  description = "Add the llm-content-safety policy to /openai (uses the Foundry resource's Content Safety capability via APIM managed identity)."
  type        = bool
  default     = false
}

variable "a2a_mode" {
  description = "How the base agent is exposed over A2A: 'native_foundry' (Foundry incoming A2A, PREVIEW) or 'adapter' (Agent Framework A2A adapter on Container Apps, FALLBACK)."
  type        = string
  default     = "native_foundry"

  validation {
    condition     = contains(["native_foundry", "adapter"], var.a2a_mode)
    error_message = "a2a_mode must be 'native_foundry' or 'adapter'."
  }
}

variable "a2a_apim_api_kind" {
  description = "APIM API flavour for /a2a/care-knowledge: 'a2a' (APIM A2A agent API, ARM shape not yet in the published schema) or 'http' (plain HTTP API with explicit card/JSON-RPC operations, FALLBACK)."
  type        = string
  default     = "a2a"

  validation {
    condition     = contains(["a2a", "http"], var.a2a_apim_api_kind)
    error_message = "a2a_apim_api_kind must be 'a2a' or 'http'."
  }
}

variable "telemetry_require_subscription_key" {
  description = "true = /telemetry requires the participant key (primary). false = FALLBACK: anonymous ingestion limited to the workshop iKey, rate-limited per IP, body-size capped (see CONTRACT §6)."
  type        = bool
  default     = true
}

variable "base_agent_model_route" {
  description = "Where the base agent's model calls go: 'apim' (Foundry AI-gateway connection to APIM, PREVIEW), 'direct' (Foundry deployment), 'auto' (try APIM, verify, fall back to direct)."
  type        = string
  default     = "auto"

  validation {
    condition     = contains(["auto", "apim", "direct"], var.base_agent_model_route)
    error_message = "base_agent_model_route must be auto, apim or direct."
  }
}

variable "knowledge_mode" {
  description = "Grounding for the base agent: 'kb' (Foundry IQ knowledge base care-kb over MCP), 'index' (FALLBACK classic index + Azure AI Search tool), 'auto' (kb, else index)."
  type        = string
  default     = "auto"

  validation {
    condition     = contains(["auto", "kb", "index"], var.knowledge_mode)
    error_message = "knowledge_mode must be auto, kb or index."
  }
}

variable "search_sku" {
  description = "Azure AI Search tier. Knowledge bases with managed-identity model access need Basic or higher; semantic ranker is not available on Free."
  type        = string
  default     = "basic"

  validation {
    condition     = contains(["basic", "standard", "standard2", "standard3"], var.search_sku)
    error_message = "search_sku must be basic or higher."
  }
}

variable "search_knowledge_retrieval_plan" {
  description = "Agentic retrieval billing plan: 'free' (monthly allowance, then HTTP 402) or 'standard' (pay-as-you-go; recommended for 30 participants)."
  type        = string
  default     = "standard"

  validation {
    condition     = contains(["free", "standard"], var.search_knowledge_retrieval_plan)
    error_message = "search_knowledge_retrieval_plan must be free or standard."
  }
}

variable "openai_api_version" {
  description = "Azure OpenAI data-plane api-version written to participant .env files (latest GA dated version at time of writing; the /openai/v1 route needs none)."
  type        = string
  default     = "2024-10-21"
}

variable "care_tools_rest_in_product" {
  description = "Also add the backing REST API care-tools-api to the participant product. Default false: participants only reach the tools through the MCP server."
  type        = bool
  default     = false
}

variable "run_post_deploy" {
  description = "Run the post-deploy scripts (container builds, knowledge seeding, base agent) via local-exec. Set false for plan-only / CI validation."
  type        = bool
  default     = true
}
