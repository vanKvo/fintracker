# XS-COMP-12: CloudFront adds the security headers; the app code sets none itself.
# Attach the policy's id to the distribution's default cache behavior (response_headers_policy_id).

locals {
  # The Phase 2.1 policy. Angular Material needs inline styles; scripts stay 'self'-only.
  csp_directives = [
    "default-src 'self'",
    "script-src 'self'",
    "connect-src ${join(" ", concat(["'self'"], var.connect_src))}",
    "style-src 'self' 'unsafe-inline'",
    "img-src ${join(" ", concat(["'self'", "data:"], var.img_src_extra))}",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
  ]
}

resource "aws_cloudfront_response_headers_policy" "this" {
  name    = var.name
  comment = "XS-COMP-12: HSTS, nosniff, referrer policy, frame denial and CSP"

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 63072000 # 2 years
      include_subdomains         = true
      preload                    = false
      override                   = true
    }
    content_type_options {
      override = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    content_security_policy {
      content_security_policy = join("; ", local.csp_directives)
      override                = true
    }
  }
}
