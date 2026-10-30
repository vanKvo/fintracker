# Account-level compliance controls (XS-COMP). `profile` follows architecture doc 6.1: it changes
# only defense-in-depth layers and cost, never the core controls.

locals {
  settings = {
    dev  = { waf = false, nist_800_53 = false }
    prod = { waf = true, nist_800_53 = true }
  }[var.profile]
}

resource "aws_sns_topic" "security_alarms" {
  name = "fintracker-${var.profile}-security-alarms"
}

resource "aws_sns_topic_policy" "security_alarms" {
  arn = aws_sns_topic.security_alarms.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventBridgePublish"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sns:Publish"
      Resource  = aws_sns_topic.security_alarms.arn
    }]
  })
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alarm_email == null ? 0 : 1

  topic_arn = aws_sns_topic.security_alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# XS-COMP-09, XS-COMP-10
module "security_baseline" {
  source = "../../modules/security_baseline"

  alarm_sns_topic_arn = aws_sns_topic.security_alarms.arn
  nist_800_53         = local.settings.nist_800_53
}

# XS-COMP-12
module "security_headers" {
  source = "../../modules/security_headers"

  name        = "fintracker-${var.profile}-security-headers"
  connect_src = var.headers_connect_src
}

# XS-COMP-13: prod only (app doc 6.1)
module "waf_cloudfront" {
  count  = local.settings.waf ? 1 : 0
  source = "../../modules/waf_managed_rules"

  name  = "fintracker-${var.profile}-cloudfront"
  scope = "CLOUDFRONT"
}

module "waf_chat_api" {
  count  = local.settings.waf ? 1 : 0
  source = "../../modules/waf_managed_rules"

  name  = "fintracker-${var.profile}-chat-api"
  scope = "REGIONAL"
}
