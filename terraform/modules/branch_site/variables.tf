variable "site_name" {
  description = "Identifier used in resource names (lowercase, no spaces)"
  type        = string
}

variable "site_display_name" {
  description = "Human-readable site name (used in Name tag)"
  type        = string
}

variable "city" {
  description = "City the site represents"
  type        = string
}

variable "state" {
  description = "Indian state the site is in"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for this site's VPC"
  type        = string
}

variable "subnet_cidr" {
  description = "CIDR block for this site's subnet"
  type        = string
}

variable "availability_zone" {
  description = "AZ to deploy into"
  type        = string
  default     = "ap-south-1a"
}

variable "instance_type" {
  description = "EC2 instance type for SD-WAN edge"
  type        = string
  default     = "t3.micro"
}

variable "transit_gateway_id" {
  description = "ID of the Transit Gateway to attach the VPN to"
  type        = string
}

variable "customer_bgp_asn" {
  description = "BGP ASN for the customer side (must be unique per site)"
  type        = number
}

variable "central_cidr" {
  description = "CIDR of the central VPC reachable over IPsec"
  type        = string
  default     = "10.0.0.0/16"
}

variable "edge_ami_id" {
  description = <<-EOT
    Pinned AMI ID for the SD-WAN edge EC2. Defaults to a tested Canonical
    Ubuntu 22.04 LTS AMI in ap-south-1 (2026-05-21 build). Pass null to
    auto-resolve the most_recent Canonical image - NOT recommended for
    demos since Canonical pushes new images daily and any of them can
    break the bootstrap (broken-AMI incident: ami-040e95ba14632401d /
    2026-06-02 shipped with awscli/ssm-agent regressions).
  EOT
  type        = string
  default     = "ami-07b301a23def3266d"
}
