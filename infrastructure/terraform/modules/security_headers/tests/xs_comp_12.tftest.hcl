# XS-COMP-12: security headers and CSP set by CloudFront. Run: terraform test (mocked AWS).

mock_provider "aws" {}

variables {
  connect_src = ["https://cognito-idp.us-east-1.amazonaws.com", "https://abc123.execute-api.us-east-1.amazonaws.com"]
}

# [Happy] A request for / returns all five headers.
run "all_five_headers_are_set" {
  command = apply

  assert {
    condition     = one(aws_cloudfront_response_headers_policy.this.security_headers_config).strict_transport_security[0].access_control_max_age_sec >= 31536000
    error_message = "Strict-Transport-Security must last at least a year."
  }
  assert {
    condition     = one(aws_cloudfront_response_headers_policy.this.security_headers_config).content_type_options[0].override == true
    error_message = "X-Content-Type-Options: nosniff must be set."
  }
  assert {
    condition     = one(aws_cloudfront_response_headers_policy.this.security_headers_config).referrer_policy[0].referrer_policy == "strict-origin-when-cross-origin"
    error_message = "Referrer-Policy must be set."
  }
  assert {
    condition     = one(aws_cloudfront_response_headers_policy.this.security_headers_config).frame_options[0].frame_option == "DENY"
    error_message = "X-Frame-Options: DENY must be set for browsers that ignore frame-ancestors."
  }
  assert {
    condition     = one(aws_cloudfront_response_headers_policy.this.security_headers_config).content_security_policy[0].override == true
    error_message = "Content-Security-Policy must be set."
  }
}

# [Fail] A script injected from an origin outside script-src is blocked by the browser: script-src
# allows only our own origin, and frames from anywhere are refused.
run "csp_allows_scripts_only_from_our_origin" {
  command = apply

  assert {
    condition = (
      contains(split("; ", output.content_security_policy), "script-src 'self'")
      && contains(split("; ", output.content_security_policy), "default-src 'self'")
      && contains(split("; ", output.content_security_policy), "frame-ancestors 'none'")
      && contains(split("; ", output.content_security_policy), "object-src 'none'")
    )
    error_message = "The CSP must restrict script-src and default-src to 'self', forbid framing and plugins."
  }
  assert {
    condition     = contains(split("; ", output.content_security_policy), "connect-src 'self' https://cognito-idp.us-east-1.amazonaws.com https://abc123.execute-api.us-east-1.amazonaws.com")
    error_message = "connect-src must list exactly the Cognito and API origins given."
  }
}
