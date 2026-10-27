# Bug name: Bedrock cost anomaly monitor fails with "Limit exceeded on dimensional spend monitor creation"

## Problem
`terraform apply` for the AI assistant `dev` environment failed creating `aws_ce_anomaly_monitor.bedrock` (`fintracker-dev-bedrock`):

`CreateAnomalyMonitor ... ValidationException: Limit exceeded on dimensional spend monitor creation`

### Root cause:
AWS allows only one DIMENSIONAL (per-service) Cost Anomaly monitor per account. The Demo account already has `Default-Services-Monitor` (DIMENSIONAL), which AWS creates by default, so a second one is rejected.

### Code with bug:
```hcl
resource "aws_ce_anomaly_monitor" "bedrock" {
  name              = "fintracker-${var.env_name}-bedrock"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
  tags              = var.tags
}
```

## Solution
A first attempt, a CUSTOM monitor filtered on `SERVICE`, was rejected with `Dimension not valid; must be scoped to 'LINKED_ACCOUNT'`: custom monitors can only filter on linked account, tags or cost categories.

A second attempt then failed creating the cost category: `Dimension SERVICE is not allowed` (cost categories allow `SERVICE_CODE`, not `SERVICE`), so the rule uses `SERVICE_CODE = AmazonBedrock`.

The fix isolates Bedrock spend in a cost category (rule: service `Amazon Bedrock`) and points a CUSTOM monitor at that category. The module test asserts the monitor references the category and the category holds Amazon Bedrock.

### Fixed Code
```hcl
resource "aws_ce_cost_category" "bedrock" {
  name         = "fintracker-${var.env_name}-bedrock"
  rule_version = "CostCategoryExpression.v1"

  rule {
    value = "bedrock"
    rule {
      dimension {
        key           = "SERVICE_CODE"
        values        = ["AmazonBedrock"]
        match_options = ["EQUALS"]
      }
    }
  }
  tags = var.tags
}

resource "aws_ce_anomaly_monitor" "bedrock" {
  name         = "fintracker-${var.env_name}-bedrock"
  monitor_type = "CUSTOM"

  monitor_specification = jsonencode({
    CostCategories = {
      Key          = aws_ce_cost_category.bedrock.name
      Values       = ["bedrock"]
      MatchOptions = ["EQUALS"]
    }
  })
  tags = var.tags
}
```
