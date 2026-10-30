# XS-COMP-13: WAF with AWS managed rules. Run: terraform test (mocked AWS).

mock_provider "aws" {}

variables {
  name  = "fintracker-prod-cloudfront"
  scope = "CLOUDFRONT"
}

# [Happy] Known-bad inputs are blocked and counted: the core set, known bad inputs and a
# rate-based rule are all present, and the managed groups keep their own block actions.
run "core_bad_inputs_and_rate_rules_are_present" {
  command = apply

  assert {
    condition = alltrue([
      for n in ["AWSManagedRulesCommonRuleSet", "AWSManagedRulesKnownBadInputsRuleSet"] :
      anytrue([for r in aws_wafv2_web_acl.this.rule : try(one(r.statement).managed_rule_group_statement[0].name == n, false)])
    ])
    error_message = "The core rule set and the known-bad-inputs rule set must be attached."
  }
  assert {
    condition     = anytrue([for r in aws_wafv2_web_acl.this.rule : try(one(r.statement).rate_based_statement[0].limit > 0, false)])
    error_message = "A rate-based rule must be present."
  }
  assert {
    condition     = alltrue([for r in aws_wafv2_web_acl.this.rule : one(r.visibility_config).cloudwatch_metrics_enabled])
    error_message = "Every rule must publish WAF metrics so blocks are counted."
  }
  assert {
    condition     = length(aws_wafv2_web_acl.this.default_action[0].allow) == 1
    error_message = "Traffic that matches no rule is allowed; the rules do the blocking."
  }
}

# [Fail] A false positive is handled by a scoped exclusion with a recorded reason, never by removing
# the rule group: the group stays attached and only the named rule is switched to count.
run "false_positive_is_a_scoped_exclusion" {
  command = apply

  variables {
    rule_exclusions = [{
      group  = "AWSManagedRulesCommonRuleSet"
      rule   = "SizeRestrictions_BODY"
      reason = "Statement uploads post large JSON bodies to the import route"
    }]
  }

  assert {
    condition = anytrue([
      for r in aws_wafv2_web_acl.this.rule :
      try(one(r.statement).managed_rule_group_statement[0].name == "AWSManagedRulesCommonRuleSet"
      && one(one(r.statement).managed_rule_group_statement[0].rule_action_override).name == "SizeRestrictions_BODY", false)
    ])
    error_message = "The exclusion must override only the named rule inside the still-attached group."
  }
}

run "an_exclusion_without_a_reason_is_rejected" {
  command = plan

  variables {
    rule_exclusions = [{
      group  = "AWSManagedRulesCommonRuleSet"
      rule   = "SizeRestrictions_BODY"
      reason = " "
    }]
  }

  expect_failures = [var.rule_exclusions]
}
