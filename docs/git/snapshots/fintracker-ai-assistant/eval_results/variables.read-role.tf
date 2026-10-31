variable "env_name" {
  description = "Environment name used in the bucket name (for example dev)."
  type        = string
}

variable "account_id" {
  description = "AWS account ID; keeps the bucket name globally unique."
  type        = string
}

variable "eval_role_name" {
  description = "The evaluation role (bedrock_invoke_roles); the only principal granted access."
  type        = string
}

variable "ci_github_subject" {
  description = "GitHub OIDC subject of pull-request checks, for example repo:OWNER/REPO:pull_request (AN-FS-22)."
  type        = string

  validation {
    condition     = can(regex("^repo:[^*]+/[^*]+:pull_request$", var.ci_github_subject))
    error_message = "The pull-request subject must name one repository and may not use wildcards."
  }
}

variable "github_oidc_provider_arn" {
  description = "ARN of the account's GitHub OIDC identity provider (token.actions.githubusercontent.com)."
  type        = string
}

variable "retention_days" {
  description = "Days a report, or a replaced report version, is kept (AN-FS-20: 90)."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
