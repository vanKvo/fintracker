# XS-COMP-13: AWS managed rules in prod, on CloudFront and the chat REST API. No custom rules until
# a finding needs one. Associate the ACL with the distribution (web_acl_id) or the API stage
# (aws_wafv2_web_acl_association) in the environment that owns them.

locals {
  managed_groups = {
    "AWSManagedRulesCommonRuleSet"         = 10
    "AWSManagedRulesKnownBadInputsRuleSet" = 20
  }
}

resource "aws_wafv2_web_acl" "this" {
  name  = var.name
  scope = var.scope

  default_action {
    allow {}
  }

  dynamic "rule" {
    for_each = local.managed_groups
    content {
      name     = rule.key
      priority = rule.value

      override_action {
        none {} # keep each rule's own action (block)
      }

      statement {
        managed_rule_group_statement {
          name        = rule.key
          vendor_name = "AWS"

          dynamic "rule_action_override" {
            for_each = [for e in var.rule_exclusions : e if e.group == rule.key]
            content {
              name = rule_action_override.value.rule
              action_to_use {
                count {}
              }
            }
          }
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.name}-${rule.key}"
        sampled_requests_enabled   = true
      }
    }
  }

  rule {
    name     = "RateLimitPerIp"
    priority = 30

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-RateLimitPerIp"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = var.name
    sampled_requests_enabled   = true
  }

  tags = var.tags
}
