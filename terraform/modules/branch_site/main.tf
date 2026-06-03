# Fallback only - used when var.edge_ami_id is null. We do NOT pick it for
# production demos because Canonical pushes new images daily; see variable doc.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  resolved_edge_ami = var.edge_ami_id != null ? var.edge_ami_id : data.aws_ami.ubuntu.id
}

data "aws_region" "current" {}

resource "aws_vpc" "site" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "vi-demo-site-${var.site_name}-vpc"
    Site = var.site_display_name
    City = var.city
  }
}

resource "aws_internet_gateway" "site" {
  vpc_id = aws_vpc.site.id

  tags = {
    Name = "vi-demo-site-${var.site_name}-igw"
  }
}

resource "aws_subnet" "site" {
  vpc_id                  = aws_vpc.site.id
  cidr_block              = var.subnet_cidr
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true

  tags = {
    Name = "vi-demo-site-${var.site_name}-subnet"
  }
}

resource "aws_route_table" "site" {
  vpc_id = aws_vpc.site.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.site.id
  }

  tags = {
    Name = "vi-demo-site-${var.site_name}-rt"
  }
}

resource "aws_route_table_association" "site" {
  subnet_id      = aws_subnet.site.id
  route_table_id = aws_route_table.site.id
}

resource "aws_security_group" "site_edge" {
  name        = "vi-demo-site-${var.site_name}-sg"
  description = "SD-WAN edge security group for ${var.site_display_name}"
  vpc_id      = aws_vpc.site.id

  ingress {
    description = "IPsec IKE"
    from_port   = 500
    to_port     = 500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "IPsec NAT-T"
    from_port   = 4500
    to_port     = 4500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "ESP (IPsec data)"
    from_port   = -1
    to_port     = -1
    protocol    = "50"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "ICMP from sibling site VPCs + central (validates SD-WAN reach)"
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "vi-demo-site-${var.site_name}-sg"
  }
}

resource "aws_iam_role" "edge_ssm" {
  name = "vi-demo-site-${var.site_name}-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "edge_ssm" {
  role       = aws_iam_role.edge_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "edge_vpn_read" {
  name = "vi-demo-site-${var.site_name}-vpn-read"
  role = aws_iam_role.edge_ssm.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ec2:DescribeVpnConnections",
        "ec2:DescribeTags",
        "ec2:DescribeInstances"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_instance_profile" "edge_ssm" {
  name = "vi-demo-site-${var.site_name}-ssm-profile"
  role = aws_iam_role.edge_ssm.name
}

resource "aws_instance" "edge" {
  ami                         = local.resolved_edge_ami
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.site.id
  vpc_security_group_ids      = [aws_security_group.site_edge.id]
  iam_instance_profile        = aws_iam_instance_profile.edge_ssm.name
  source_dest_check           = false
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/edge-bootstrap.sh.tftpl", {
    site_name    = var.site_name
    aws_region   = data.aws_region.current.name
    site_cidr    = var.vpc_cidr
    central_cidr = var.central_cidr
  })
  user_data_replace_on_change = true

  # Make sure the IAM role's policies are fully attached BEFORE the EC2 boots.
  # `iam_instance_profile` only creates an implicit dep on the profile - not on
  # the role's attached policies. Without these explicit deps Terraform can race
  # the EC2 launch against AWS IAM propagation (typically 1-10 min), causing the
  # bootstrap's `aws sts get-caller-identity` / describe-vpn-connections calls
  # to 401 silently.
  depends_on = [
    aws_iam_role_policy_attachment.edge_ssm,
    aws_iam_role_policy.edge_vpn_read,
  ]

  tags = {
    Name = "vi-demo-site-${var.site_name}-edge"
    Role = "sdwan-edge-simulator"
    Site = var.site_display_name
  }
}

resource "aws_eip" "edge" {
  domain   = "vpc"
  instance = aws_instance.edge.id

  tags = {
    Name = "vi-demo-site-${var.site_name}-eip"
  }

  depends_on = [aws_internet_gateway.site]
}

resource "aws_customer_gateway" "site" {
  bgp_asn    = var.customer_bgp_asn
  ip_address = aws_eip.edge.public_ip
  type       = "ipsec.1"

  tags = {
    Name = "vi-demo-site-${var.site_name}-cgw"
    Site = var.site_display_name
  }
}

resource "aws_vpn_connection" "site" {
  customer_gateway_id = aws_customer_gateway.site.id
  transit_gateway_id  = var.transit_gateway_id
  type                = "ipsec.1"
  static_routes_only  = true

  tags = {
    Name = "vi-demo-site-${var.site_name}-vpn"
    Site = var.site_display_name
  }
}

resource "aws_ec2_transit_gateway_route" "site_to_central" {
  destination_cidr_block         = aws_vpc.site.cidr_block
  transit_gateway_route_table_id = data.aws_ec2_transit_gateway.main.association_default_route_table_id
  transit_gateway_attachment_id  = aws_vpn_connection.site.transit_gateway_attachment_id
}

data "aws_ec2_transit_gateway" "main" {
  id = var.transit_gateway_id
}
