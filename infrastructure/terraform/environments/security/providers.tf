terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local backend, as the Data pipeline's dev environment: single developer, one state per account.
  # Move to a shared backend when a second person deploys.
  backend "local" {
    path = "terraform.tfstate"
  }
}

# CloudFront-scope WAF and CloudFront policies live in us-east-1; the default region here is also
# us-east-1 (the app's region), so one provider serves both.
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "fintracker"
      Component = "compliance-controls"
      Profile   = var.profile
      ManagedBy = "terraform"
    }
  }
}
