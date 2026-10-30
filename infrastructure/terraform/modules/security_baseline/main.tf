# XS-COMP-09 Security Hub CSPM and XS-COMP-10 Inspector: continuous configuration and vulnerability
# checks, owned by AWS. FinTracker's part is fixing findings and getting told about the serious ones.
# One instance per AWS account and region.

data "aws_region" "current" {}

resource "aws_securityhub_account" "this" {
  # The standards below are enabled explicitly, so the broader default set stays off.
  enable_default_standards = false
}

locals {
  standards = merge(
    { foundational = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0" },
    var.nist_800_53 ? { nist_800_53 = "arn:aws:securityhub:${data.aws_region.current.name}::standards/nist-800-53/v/5.0.0" } : {},
  )
}

resource "aws_securityhub_standards_subscription" "this" {
  for_each = local.standards

  standards_arn = each.value
  depends_on    = [aws_securityhub_account.this]
}

# XS-COMP-10: Lambda packages and code, and container images. Findings flow into Security Hub.
resource "aws_inspector2_enabler" "this" {
  account_ids    = [data.aws_caller_identity.current.account_id]
  resource_types = ["LAMBDA", "LAMBDA_CODE", "ECR"]
}

data "aws_caller_identity" "current" {}

# A new critical or high finding alarms as soon as Security Hub imports it.
resource "aws_cloudwatch_event_rule" "findings" {
  name        = "security-hub-critical-high-findings"
  description = "XS-COMP-09/10: new critical and high findings alarm"
  event_pattern = jsonencode({
    source        = ["aws.securityhub"]
    "detail-type" = ["Security Hub Findings - Imported"]
    detail = {
      findings = {
        Severity    = { Label = ["CRITICAL", "HIGH"] }
        Workflow    = { Status = ["NEW"] }
        RecordState = ["ACTIVE"]
      }
    }
  })
  tags = var.tags
}

resource "aws_cloudwatch_event_target" "findings_to_alarm" {
  rule = aws_cloudwatch_event_rule.findings.name
  arn  = var.alarm_sns_topic_arn
}
