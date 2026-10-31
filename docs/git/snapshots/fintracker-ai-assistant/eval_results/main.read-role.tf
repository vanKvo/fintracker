# AN-FS-22: evaluation reports. The CLI reads the last pass per prompt version, model and tier (tier
# order and change-vs-last-pass) and writes one report per run; only the eval role may write.
# The pull-request check reads through a separate read-only role (no Bedrock access).
# Reports hold fixture names, token counts, costs and latencies: synthetic data, no user data.

resource "aws_s3_bucket" "results" {
  bucket = "fintracker-ai-assistant-${var.env_name}-eval-results-${var.account_id}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket                  = aws_s3_bucket.results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# AN-FS-20 data table: versioned, 90-day lifecycle. Reports, and overwritten "last pass" pointers,
# expire 90 days after they were written or replaced; a run then has to pass its tiers again.
resource "aws_s3_bucket_versioning" "results" {
  bucket = aws_s3_bucket.results.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    id     = "expire-after-retention"
    status = "Enabled"
    filter {}
    expiration {
      days = var.retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = var.retention_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.results.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.results.arn, "${aws_s3_bucket.results.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.results]
}

# Get and put only: the CLI never lists or deletes. ListBucket is granted so a missing pointer
# reads as NoSuchKey (first run) instead of AccessDenied.
resource "aws_iam_role_policy" "eval_results" {
  name = "eval-results"
  role = var.eval_role_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadWriteReports"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.results.arn}/*"
      },
      {
        Sid      = "MissingKeyIsNoSuchKey"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.results.arn
      },
    ]
  })
}

# AN-FS-22: the pull-request check (ci.yml, eval-required) reads reports to decide whether a PR can merge.
# Trusted only from pull-request runs of this repository. Read only: no Bedrock actions, no writes.
resource "aws_iam_role" "ci_results_read" {
  name = "fintracker-ai-assistant-${var.env_name}-ci-results-read"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.github_oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = var.ci_github_subject
        }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "ci_results_read" {
  name = "eval-results-read"
  role = aws_iam_role.ci_results_read.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadReports"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.results.arn}/*"
      },
      {
        Sid      = "MissingKeyIsNoSuchKey"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.results.arn
      },
    ]
  })
}
