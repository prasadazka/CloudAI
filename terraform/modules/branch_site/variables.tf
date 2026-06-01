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
