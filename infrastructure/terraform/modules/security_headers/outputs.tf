output "policy_id" {
  value = aws_cloudfront_response_headers_policy.this.id
}

output "content_security_policy" {
  value = join("; ", local.csp_directives)
}
