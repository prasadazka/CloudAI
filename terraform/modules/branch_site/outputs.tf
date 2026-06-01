output "vpc_id" {
  description = "ID of the site VPC"
  value       = aws_vpc.site.id
}

output "subnet_id" {
  description = "ID of the site subnet"
  value       = aws_subnet.site.id
}

output "instance_id" {
  description = "EC2 instance ID of the SD-WAN edge"
  value       = aws_instance.edge.id
}

output "edge_public_ip" {
  description = "Elastic IP of the SD-WAN edge (used for VPN Customer Gateway)"
  value       = aws_eip.edge.public_ip
}

output "security_group_id" {
  description = "Security group ID for the SD-WAN edge"
  value       = aws_security_group.site_edge.id
}

output "vpc_cidr" {
  description = "CIDR of the site VPC"
  value       = aws_vpc.site.cidr_block
}

output "vpn_connection_id" {
  description = "ID of the Site-to-Site VPN connection"
  value       = aws_vpn_connection.site.id
}

output "customer_gateway_id" {
  description = "ID of the Customer Gateway"
  value       = aws_customer_gateway.site.id
}
