variable "central_vpc_cidr" {
  description = "CIDR block for the central (HQ) VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "central_public_subnet_cidr" {
  description = "CIDR for public subnet in central VPC"
  type        = string
  default     = "10.0.1.0/24"
}

variable "central_private_subnet_cidr" {
  description = "CIDR for private subnet in central VPC"
  type        = string
  default     = "10.0.2.0/24"
}

variable "availability_zone" {
  description = "AZ to deploy subnets into (single AZ for demo simplicity)"
  type        = string
  default     = "ap-south-1a"
}
