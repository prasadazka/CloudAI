terraform {
  backend "s3" {
    bucket       = "vi-demo-tfstate-877326605600"
    key          = "demo/terraform.tfstate"
    region       = "ap-south-1"
    profile      = "vi-demo"
    encrypt      = true
    use_lockfile = true
  }
}
