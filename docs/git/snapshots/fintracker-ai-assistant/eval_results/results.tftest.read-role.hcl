# AN-FS-22: pull-request checks read evaluation reports through a read-only role with no Bedrock access.

mock_provider "aws" {}

variables {
  env_name                 = "test"
  account_id               = "123456789012"
  eval_role_name           = "fintracker-ai-assistant-test-eval"
  ci_github_subject        = "repo:owner/fintracker:pull_request"
  github_oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
}

run "the_read_role_is_assumable_only_from_pull_request_checks" {
  command = plan

  assert {
    condition     = jsondecode(aws_iam_role.ci_results_read.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:owner/fintracker:pull_request"
    error_message = "Only the pull-request checks may assume the read-only results role."
  }

  assert {
    condition     = jsondecode(aws_iam_role.ci_results_read.assume_role_policy).Statement[0].Action == "sts:AssumeRoleWithWebIdentity"
    error_message = "The read-only results role is assumed through OIDC, not with stored credentials."
  }
}

run "the_read_role_can_get_reports_and_list_the_bucket_only" {
  command = apply

  assert {
    condition     = jsondecode(aws_iam_role_policy.ci_results_read.policy).Statement[0].Action == "s3:GetObject"
    error_message = "The pull-request checks only read reports."
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.ci_results_read.policy).Statement[1].Action == "s3:ListBucket"
    error_message = "ListBucket is needed so a missing pointer reads as NoSuchKey."
  }

  assert {
    condition     = length(regexall("s3:PutObject|s3:DeleteObject", aws_iam_role_policy.ci_results_read.policy)) == 0
    error_message = "The read-only role must not write or delete reports."
  }
}

run "the_read_role_holds_no_bedrock_permissions" {
  command = apply

  assert {
    condition     = length(regexall("bedrock", aws_iam_role_policy.ci_results_read.policy)) == 0
    error_message = "No Bedrock access is granted to the pull-request checks."
  }
}

run "a_wildcard_pull_request_subject_is_refused" {
  command = plan
  variables { ci_github_subject = "repo:*/*:pull_request" }
  expect_failures = [var.ci_github_subject]
}
