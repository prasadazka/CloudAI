module "pune_retail_01" {
  source = "../../modules/branch_site"

  site_name          = "pune-retail-01"
  site_display_name  = "Pune Retail 01"
  city               = "Pune"
  state              = "Maharashtra"
  vpc_cidr           = "10.1.0.0/16"
  subnet_cidr        = "10.1.1.0/24"
  transit_gateway_id = aws_ec2_transit_gateway.main.id
  customer_bgp_asn   = 65001
}

output "pune_retail_01_edge_ip" {
  description = "Public IP of Pune Retail 01 SD-WAN edge"
  value       = module.pune_retail_01.edge_public_ip
}

output "pune_retail_01_instance_id" {
  description = "EC2 instance ID of Pune Retail 01 edge"
  value       = module.pune_retail_01.instance_id
}

output "pune_retail_01_vpn_id" {
  description = "VPN connection ID of Pune Retail 01"
  value       = module.pune_retail_01.vpn_connection_id
}
