# XS-COMP-09 (Security Hub CSPM) and XS-COMP-10 (Inspector). Run: terraform test (mocked AWS).

mock_provider "aws" {
  mock_data "aws_region" {
    defaults = { name = "us-east-1" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
}

variables {
  alarm_sns_topic_arn = "arn:aws:sns:us-east-1:123456789012:alarms"
}

# Requirement: Security Hub is on with the AWS Foundational Security Best Practices standard.
run "foundational_standard_is_always_on" {
  command = apply

  assert {
    condition     = length([for s in aws_securityhub_standards_subscription.this : s if endswith(s.standards_arn, "/aws-foundational-security-best-practices/v/1.0.0")]) == 1
    error_message = "Foundational Security Best Practices must be subscribed."
  }
}

# [Alt] Dev may run Foundational Security Best Practices only, to save cost.
run "dev_runs_only_the_foundational_standard" {
  command = apply

  variables {
    nist_800_53 = false
  }

  assert {
    condition     = length(aws_securityhub_standards_subscription.this) == 1
    error_message = "Without nist_800_53 only one standard may be subscribed."
  }
}

# Requirement: prod adds NIST SP 800-53 Rev. 5.
run "prod_adds_nist_800_53" {
  command = apply

  variables {
    nist_800_53 = true
  }

  assert {
    condition     = length([for s in aws_securityhub_standards_subscription.this : s if endswith(s.standards_arn, "/nist-800-53/v/5.0.0")]) == 1
    error_message = "NIST SP 800-53 Rev. 5 must be subscribed in prod."
  }
}

# [Fail] A new critical (or high) finding alarms: every new, active critical/high finding goes to
# the alarm topic as soon as it is imported (well inside the 1 hour limit).
run "new_critical_and_high_findings_alarm" {
  command = apply

  assert {
    condition = (
      jsondecode(aws_cloudwatch_event_rule.findings.event_pattern)["detail-type"] == ["Security Hub Findings - Imported"]
      && toset(jsondecode(aws_cloudwatch_event_rule.findings.event_pattern).detail.findings.Severity.Label) == toset(["CRITICAL", "HIGH"])
      && jsondecode(aws_cloudwatch_event_rule.findings.event_pattern).detail.findings.Workflow.Status == ["NEW"]
    )
    error_message = "The rule must match new CRITICAL and HIGH findings."
  }
  assert {
    condition     = aws_cloudwatch_event_target.findings_to_alarm.arn == "arn:aws:sns:us-east-1:123456789012:alarms"
    error_message = "Findings must go to the alarm topic."
  }
}

# XS-COMP-10: Inspector scans Lambda functions (packages and code) and container images.
run "inspector_scans_functions_and_images" {
  command = apply

  assert {
    condition     = toset(aws_inspector2_enabler.this.resource_types) == toset(["LAMBDA", "LAMBDA_CODE", "ECR"])
    error_message = "Inspector must scan Lambda functions, Lambda code and ECR images."
  }
}
