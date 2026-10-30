variable "name" {
  type = string
}

variable "scope" {
  description = "CLOUDFRONT (create in us-east-1) or REGIONAL (the chat REST API stage)."
  type        = string
  validation {
    condition     = contains(["CLOUDFRONT", "REGIONAL"], var.scope)
    error_message = "scope must be CLOUDFRONT or REGIONAL."
  }
}

variable "rate_limit" {
  description = "Requests per 5 minutes per source IP before the rate rule blocks."
  type        = number
  default     = 2000
}

variable "rule_exclusions" {
  description = "Scoped exclusions for a false positive: one rule inside a managed group is switched to count. Never remove a group. The reason is recorded in the rule's metric name's description and is mandatory."
  type = list(object({
    group  = string
    rule   = string
    reason = string
  }))
  default = []

  validation {
    condition     = alltrue([for e in var.rule_exclusions : length(trimspace(e.reason)) > 0])
    error_message = "Every rule exclusion needs a written reason."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
