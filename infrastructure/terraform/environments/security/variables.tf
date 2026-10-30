variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile to deploy with (dev or prod account)."
  type        = string
  default     = null
}

variable "profile" {
  description = "Deployment profile (architecture doc 6.1): dev or prod."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.profile)
    error_message = "profile must be dev or prod."
  }
}

variable "headers_connect_src" {
  description = "XS-COMP-12: origins the SPA may call: the Cognito endpoint and the API origin(s)."
  type        = list(string)
}

variable "alarm_email" {
  description = "Optional address subscribed to the security alarm topic. Confirm the subscription by email."
  type        = string
  default     = null
}
