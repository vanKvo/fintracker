variable "name" {
  type    = string
  default = "fintracker-security-headers"
}

variable "connect_src" {
  description = "Origins the app may call besides itself: the Cognito endpoint and the API origin(s) (Phase 2.1)."
  type        = list(string)
}

variable "img_src_extra" {
  description = "Extra image origins, beyond 'self' and data: URIs."
  type        = list(string)
  default     = []
}
