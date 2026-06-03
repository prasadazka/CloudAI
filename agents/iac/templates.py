"""
Terraform code templates for IaC Agent.
Each function returns the file content as a string.
"""

import re


def _safe_name(s: str) -> str:
    """Convert any string to a Terraform-safe identifier."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.lower()).strip("_")
    return s or "site"


def render_backend(workflow_id: str) -> str:
    return f"""terraform {{
  backend "s3" {{
    bucket       = "vi-demo-tfstate-877326605600"
    key          = "workflows/{workflow_id}/terraform.tfstate"
    region       = "ap-south-1"
    profile      = "vi-demo"
    encrypt      = true
    use_lockfile = true
  }}
}}
"""


def render_provider(workflow_id: str, customer_name: str) -> str:
    return f"""terraform {{
  required_version = ">= 1.5.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region  = "ap-south-1"
  profile = "vi-demo"

  default_tags {{
    tags = {{
      Project    = "ViDemo"
      ManagedBy  = "Terraform"
      WorkflowID = "{workflow_id}"
      Customer   = "{customer_name}"
      AutoStop   = "true"
    }}
  }}
}}
"""


def render_central_vpc() -> str:
    return """resource "aws_vpc" "central" {
  cidr_block           = "10.0.0.0/16"
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
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "ap-south-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "vi-demo-central-public"
  }
}

resource "aws_subnet" "central_private" {
  vpc_id            = aws_vpc.central.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "ap-south-1a"

  tags = {
    Name = "vi-demo-central-private"
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
"""


def render_tgw() -> str:
    return """resource "aws_ec2_transit_gateway" "main" {
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
"""


def render_site_module_block(
    index: int, city: str, state: str, bandwidth_mbps: int, module_path: str
) -> str:
    """One terraform module block per site. Index is 1-based for CIDR allocation."""
    name = _safe_name(f"{city}_{index:02d}")
    site_kebab = name.replace("_", "-")
    return f"""module "{name}" {{
  source = "{module_path}"

  site_name          = "{site_kebab}"
  site_display_name  = "{city} #{index:02d}"
  city               = "{city}"
  state              = "{state or 'Unknown'}"
  vpc_cidr           = "10.{index}.0.0/16"
  subnet_cidr        = "10.{index}.1.0/24"
  central_cidr       = "10.0.0.0/16"
  transit_gateway_id = aws_ec2_transit_gateway.main.id
  customer_bgp_asn   = {65000 + index}
}}
"""


def render_sites_file(sites, module_path: str) -> str:
    """Render the full sites.tf file with all module calls."""
    blocks = []
    outputs = []
    for i, s in enumerate(sites, 1):
        blocks.append(
            render_site_module_block(
                i, s.city, s.state, s.bandwidth_mbps, module_path
            )
        )
        name = _safe_name(f"{s.city}_{i:02d}")
        outputs.append(
            f'output "{name}_edge_ip" {{\n'
            f'  value = module.{name}.edge_public_ip\n'
            f"}}\n"
        )
    return "\n".join(blocks) + "\n" + "\n".join(outputs)
