resource "aws_vpc" "central" {
  cidr_block           = var.central_vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "vi-demo-central-vpc"
    Role = "customer-hq"
  }
}

resource "aws_internet_gateway" "central" {
  vpc_id = aws_vpc.central.id

  tags = {
    Name = "vi-demo-central-igw"
  }
}

resource "aws_subnet" "central_public" {
  vpc_id                  = aws_vpc.central.id
  cidr_block              = var.central_public_subnet_cidr
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true

  tags = {
    Name = "vi-demo-central-public"
    Tier = "public"
  }
}

resource "aws_subnet" "central_private" {
  vpc_id            = aws_vpc.central.id
  cidr_block        = var.central_private_subnet_cidr
  availability_zone = var.availability_zone

  tags = {
    Name = "vi-demo-central-private"
    Tier = "private"
  }
}

resource "aws_route_table" "central_public" {
  vpc_id = aws_vpc.central.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.central.id
  }

  tags = {
    Name = "vi-demo-central-public-rt"
  }
}

resource "aws_route_table_association" "central_public" {
  subnet_id      = aws_subnet.central_public.id
  route_table_id = aws_route_table.central_public.id
}

resource "aws_route_table" "central_private" {
  vpc_id = aws_vpc.central.id

  route {
    cidr_block         = "10.0.0.0/8"
    transit_gateway_id = aws_ec2_transit_gateway.main.id
  }

  tags = {
    Name = "vi-demo-central-private-rt"
  }

  depends_on = [aws_ec2_transit_gateway_vpc_attachment.central]
}

resource "aws_route_table_association" "central_private" {
  subnet_id      = aws_subnet.central_private.id
  route_table_id = aws_route_table.central_private.id
}
