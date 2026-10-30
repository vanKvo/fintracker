output "alarm_topic_arn" {
  value = aws_sns_topic.security_alarms.arn
}

output "response_headers_policy_id" {
  description = "Set as response_headers_policy_id on the CloudFront distribution's default cache behavior."
  value       = module.security_headers.policy_id
}

output "cloudfront_web_acl_arn" {
  description = "Set as web_acl_id on the CloudFront distribution (prod)."
  value       = one(module.waf_cloudfront[*].web_acl_arn)
}

output "chat_api_web_acl_arn" {
  description = "Associate with the chat REST API stage (prod)."
  value       = one(module.waf_chat_api[*].web_acl_arn)
}
