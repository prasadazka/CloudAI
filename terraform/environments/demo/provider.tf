terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = "ap-south-1"
  profile = "vi-demo"

  default_tags {
    tags = {
      Project   = "ViDemo"
      ManagedBy = "Terraform"
      Owner     = "biz-ops@azkashine.com"
      AutoStop  = "true"
    }
  }
}
