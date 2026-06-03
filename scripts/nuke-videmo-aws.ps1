# Emergency cleanup — deletes ALL AWS resources tagged Project=ViDemo
# in ap-south-1. Use after a failed terraform apply leaves orphans.
#
# Run: powershell -ExecutionPolicy Bypass -File scripts\nuke-videmo-aws.ps1
#
# DOES NOT TOUCH: S3 state bucket, DynamoDB lock table, IAM user (foundation)

$ErrorActionPreference = "Continue"
$profile = "vi-demo"
$region = "ap-south-1"

function tag-filter {
    @("Name=tag:Name,Values=vi-demo-*")
}

Write-Host "==> Step 1: Terminate EC2 instances tagged ViDemo" -ForegroundColor Cyan
$ids = (aws ec2 describe-instances `
    --filters "Name=tag:Name,Values=vi-demo-*" "Name=instance-state-name,Values=running,pending,stopping,stopped" `
    --query "Reservations[].Instances[].InstanceId" --output text `
    --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
if ($ids) {
    Write-Host "   terminating: $($ids -join ', ')"
    aws ec2 terminate-instances --instance-ids $ids --profile $profile --region $region | Out-Null
    Write-Host "   waiting for termination..."
    aws ec2 wait instance-terminated --instance-ids $ids --profile $profile --region $region
}

Write-Host "==> Step 2: Release Elastic IPs" -ForegroundColor Cyan
$eips = (aws ec2 describe-addresses --filters "Name=tag:Name,Values=vi-demo-*" `
    --query "Addresses[].AllocationId" --output text `
    --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
foreach ($a in $eips) {
    Write-Host "   releasing $a"
    aws ec2 release-address --allocation-id $a --profile $profile --region $region 2>&1 | Out-Null
}

Write-Host "==> Step 3: Delete Site-to-Site VPN Connections" -ForegroundColor Cyan
$vpns = (aws ec2 describe-vpn-connections --filters "Name=tag:Name,Values=vi-demo-*" "Name=state,Values=available,pending,deleting" `
    --query "VpnConnections[].VpnConnectionId" --output text `
    --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
foreach ($v in $vpns) {
    Write-Host "   deleting $v"
    aws ec2 delete-vpn-connection --vpn-connection-id $v --profile $profile --region $region 2>&1 | Out-Null
}

Write-Host "==> Step 4: Delete Customer Gateways" -ForegroundColor Cyan
$cgws = (aws ec2 describe-customer-gateways --filters "Name=tag:Name,Values=vi-demo-*" "Name=state,Values=available" `
    --query "CustomerGateways[].CustomerGatewayId" --output text `
    --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
foreach ($c in $cgws) {
    Write-Host "   deleting $c"
    aws ec2 delete-customer-gateway --customer-gateway-id $c --profile $profile --region $region 2>&1 | Out-Null
}

Write-Host "==> Step 5: Delete Transit Gateway attachments + TGWs" -ForegroundColor Cyan
$tgwAttachs = (aws ec2 describe-transit-gateway-attachments --filters "Name=tag:Name,Values=vi-demo-*" "Name=state,Values=available,pending" `
    --query "TransitGatewayAttachments[].TransitGatewayAttachmentId" --output text `
    --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
foreach ($a in $tgwAttachs) {
    Write-Host "   deleting attachment $a"
    aws ec2 delete-transit-gateway-vpc-attachment --transit-gateway-attachment-id $a --profile $profile --region $region 2>&1 | Out-Null
}
Start-Sleep -Seconds 30   # let attachments detach

$tgws = (aws ec2 describe-transit-gateways --filters "Name=tag:Name,Values=vi-demo-*" "Name=state,Values=available,pending" `
    --query "TransitGateways[].TransitGatewayId" --output text `
    --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
foreach ($t in $tgws) {
    Write-Host "   deleting TGW $t"
    aws ec2 delete-transit-gateway --transit-gateway-id $t --profile $profile --region $region 2>&1 | Out-Null
}

Write-Host "==> Step 6: Delete VPCs (drops subnets, RTs, IGWs, SGs cascade)" -ForegroundColor Cyan
$vpcs = (aws ec2 describe-vpcs --filters "Name=tag:Name,Values=vi-demo-*" `
    --query "Vpcs[].VpcId" --output text `
    --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
foreach ($vpc in $vpcs) {
    Write-Host "   draining VPC $vpc"
    # Detach + delete IGWs
    $igws = (aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vpc" --query "InternetGateways[].InternetGatewayId" --output text --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
    foreach ($i in $igws) {
        aws ec2 detach-internet-gateway --internet-gateway-id $i --vpc-id $vpc --profile $profile --region $region 2>&1 | Out-Null
        aws ec2 delete-internet-gateway --internet-gateway-id $i --profile $profile --region $region 2>&1 | Out-Null
    }
    # Delete subnets
    $subs = (aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" --query "Subnets[].SubnetId" --output text --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
    foreach ($s in $subs) {
        aws ec2 delete-subnet --subnet-id $s --profile $profile --region $region 2>&1 | Out-Null
    }
    # Delete non-default route tables
    $rts = (aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc" --query "RouteTables[?Associations[0].Main!=`true`].RouteTableId" --output text --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
    foreach ($rt in $rts) {
        aws ec2 delete-route-table --route-table-id $rt --profile $profile --region $region 2>&1 | Out-Null
    }
    # Delete non-default SGs
    $sgs = (aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc" --query "SecurityGroups[?GroupName!='default'].GroupId" --output text --profile $profile --region $region) -split "\s+" | Where-Object { $_ }
    foreach ($sg in $sgs) {
        aws ec2 delete-security-group --group-id $sg --profile $profile --region $region 2>&1 | Out-Null
    }
    # Finally, the VPC itself
    Write-Host "   deleting VPC $vpc"
    aws ec2 delete-vpc --vpc-id $vpc --profile $profile --region $region 2>&1 | Out-Null
}

Write-Host "==> Step 7: Delete IAM instance profiles + roles tagged ViDemo" -ForegroundColor Cyan
$profiles = (aws iam list-instance-profiles --query "InstanceProfiles[?contains(InstanceProfileName, 'vi-demo')].InstanceProfileName" --output text --profile $profile) -split "\s+" | Where-Object { $_ }
foreach ($p in $profiles) {
    $roles = (aws iam get-instance-profile --instance-profile-name $p --query "InstanceProfile.Roles[].RoleName" --output text --profile $profile) -split "\s+" | Where-Object { $_ }
    foreach ($r in $roles) {
        aws iam remove-role-from-instance-profile --instance-profile-name $p --role-name $r --profile $profile 2>&1 | Out-Null
    }
    aws iam delete-instance-profile --instance-profile-name $p --profile $profile 2>&1 | Out-Null
}
$roles = (aws iam list-roles --query "Roles[?contains(RoleName, 'vi-demo')].RoleName" --output text --profile $profile) -split "\s+" | Where-Object { $_ }
foreach ($r in $roles) {
    $pols = (aws iam list-attached-role-policies --role-name $r --query "AttachedPolicies[].PolicyArn" --output text --profile $profile) -split "\s+" | Where-Object { $_ }
    foreach ($pa in $pols) {
        aws iam detach-role-policy --role-name $r --policy-arn $pa --profile $profile 2>&1 | Out-Null
    }
    $inline = (aws iam list-role-policies --role-name $r --query "PolicyNames" --output text --profile $profile) -split "\s+" | Where-Object { $_ }
    foreach ($ip in $inline) {
        aws iam delete-role-policy --role-name $r --policy-name $ip --profile $profile 2>&1 | Out-Null
    }
    aws iam delete-role --role-name $r --profile $profile 2>&1 | Out-Null
}

Write-Host ""
Write-Host "DONE. Run this to verify nothing remains:" -ForegroundColor Green
Write-Host '  aws ec2 describe-instances --filters "Name=tag:Name,Values=vi-demo-*" "Name=instance-state-name,Values=running,stopped,pending" --query "Reservations[].Instances[].InstanceId" --output text --profile vi-demo --region ap-south-1'
