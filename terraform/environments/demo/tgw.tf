resource "aws_ec2_transit_gateway" "main" {
  description                     = "Vi demo TGW - hub for central VPC and branch sites"
  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  dns_support                     = "enable"

  tags = {
    Name = "vi-demo-tgw"
  }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "central" {
  transit_gateway_id = aws_ec2_transit_gateway.main.id
  vpc_id             = aws_vpc.central.id
  subnet_ids         = [aws_subnet.central_private.id]

  tags = {
    Name = "vi-demo-tgw-attach-central"
  }
}
