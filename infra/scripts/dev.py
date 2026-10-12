"""Atajos para el día a día. Uso: python infra/scripts/dev.py <comando>

  sg-open | sg-close | sg-status   Abre/cierra 5432 a 0.0.0.0/0 (RDS sin VPC)
  deploy-backend [tag]             build + push + update-function-code + env
  deploy-frontend                  build Vite + s3 sync + invalidación
  smoke                            prueba rápida vía CloudFront

Requiere: aws CLI con credenciales, docker (buildx), npm.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REGION = os.environ.get("AWS_REGION", "eu-west-1")
FUNCTION = "stockassistant-api"
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "BackEnd" / "apps" / "MonoliticDataStructure" / "app"
FRONT = ROOT / "Frontend"


def run(cmd, cwd=None, env=None, capture=False):
    print("> " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=capture, shell=(os.name == "nt"))
    if r.returncode:
        sys.exit(r.stderr.strip() if capture and r.stderr else f"Fallo: {cmd[0]}")
    return r.stdout.strip() if capture else ""


def aws(*args):
    return run(["aws", *args, "--region", REGION, "--output", "text"], capture=True)


def account():
    return aws("sts", "get-caller-identity", "--query", "Account")


def sg_id():
    name = os.environ.get("RDS_ID", "stockassistant-prod")
    return aws("rds", "describe-db-instances", "--db-instance-identifier", name,
               "--query", "DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId")


def sg(action):
    gid = sg_id()
    base = ["--group-id", gid, "--protocol", "tcp", "--port", "5432", "--cidr", "0.0.0.0/0"]
    if action == "open":
        run(["aws", "ec2", "authorize-security-group-ingress", *base, "--region", REGION])
    elif action == "close":
        run(["aws", "ec2", "revoke-security-group-ingress", *base, "--region", REGION])
    print(aws("ec2", "describe-security-groups", "--group-ids", gid,
              "--query", "SecurityGroups[0].IpPermissions[0].IpRanges[].CidrIp"))


def deploy_backend(tag=None):
    tag = tag or time.strftime("%Y%m%d-%H%M%S")
    registry = f"{account()}.dkr.ecr.{REGION}.amazonaws.com"
    image = f"{registry}/stockassistant-api:{tag}"
    pwd = aws("ecr", "get-login-password")
    subprocess.run(["docker", "login", "--username", "AWS", "--password-stdin", registry],
                   input=pwd, text=True, check=True)
    run(["docker", "buildx", "build", "--provenance=false", "--sbom=false", "--platform", "linux/amd64",
         "-f", "Dockerfile.lambda", "--build-arg", "REQUIREMENTS_FILE=requirements/lambda.txt",
         "--build-arg", "APP_MODULE=src.api.main:app", "-t", image, "--push", "."], cwd=BACKEND)
    run(["aws", "lambda", "update-function-code", "--function-name", FUNCTION, "--image-uri", image,
         "--region", REGION, "--query", "LastUpdateStatus"])
    run(["aws", "lambda", "wait", "function-updated", "--function-name", FUNCTION, "--region", REGION])
    print(f"OK {image}")


def distribution_id():
    q = "DistributionList.Items[?contains(Origins.Items[].DomainName, 'frontend-')].Id | [0]"
    return aws("cloudfront", "list-distributions", "--query", q)


def deploy_frontend():
    bucket = f"frontend-{account()}-{REGION}-an"
    env = os.environ.copy()
    env["VITE_GOOGLE_CLIENT_ID"] = aws("ssm", "get-parameter", "--name", "/stockassistant/prod/google_client_id",
                                       "--with-decryption", "--query", "Parameter.Value")
    run(["npm", "ci"], cwd=FRONT)
    run(["npm", "run", "build"], cwd=FRONT, env=env)
    run(["aws", "s3", "sync", "dist", f"s3://{bucket}", "--delete", "--region", REGION], cwd=FRONT)
    run(["aws", "cloudfront", "create-invalidation", "--distribution-id", distribution_id(), "--paths", "/*"])


def smoke():
    domain = aws("cloudfront", "get-distribution", "--id", distribution_id(),
                 "--query", "Distribution.DomainName")
    key = aws("ssm", "get-parameter", "--name", "/stockassistant/prod/api_keys", "--with-decryption",
              "--query", "Parameter.Value").split(",")[0]
    out = run(["curl", "-s", "-m", "60", "-w", "\nHTTP %{http_code} %{time_total}s", "-H", f"X-API-Key: {key}",
               f"https://{domain}/api/v1/products/?limit=1"], capture=True)
    print(out[-200:])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd in ("sg-open", "sg-close", "sg-status"):
        sg(cmd.split("-")[1])
    elif cmd == "deploy-backend":
        deploy_backend(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "deploy-frontend":
        deploy_frontend()
    elif cmd == "smoke":
        smoke()
    else:
        sys.exit(__doc__)
