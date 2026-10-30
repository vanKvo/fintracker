variable "alarm_sns_topic_arn" {
  description = "Topic that receives new critical and high findings. Must allow events.amazonaws.com to publish."
  type        = string
}

variable "nist_800_53" {
  description = "Also subscribe NIST SP 800-53 Rev. 5. On in prod; dev may run Foundational Security Best Practices only to save cost (XS-COMP-09)."
  type        = bool
  default     = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
