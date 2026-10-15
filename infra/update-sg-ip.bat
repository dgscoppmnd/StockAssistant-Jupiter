@echo off
set R=eu-west-1
set SG=sg-09db143fecffd231a
for /f %%i in ('curl -s https://checkip.amazonaws.com') do set NEW=%%i

rem Revoca las reglas 5432 existentes
for /f %%c in ('aws ec2 describe-security-groups --group-ids %SG% --region %R% --query "SecurityGroups[0].IpPermissions[?FromPort==`5432`].IpRanges[].CidrIp" --output text') do (
  aws ec2 revoke-security-group-ingress --group-id %SG% --protocol tcp --port 5432 --cidr %%c --region %R%
)
aws ec2 authorize-security-group-ingress --group-id %SG% --protocol tcp --port 5432 --cidr %NEW%/32 --region %R%
echo Regla actualizada a %NEW%/32