# Bootstrap: estado remoto de Terraform y acceso OIDC de GitHub Actions.
# Se aplica UNA vez en local (estado local). No mezclar con infra/envs/prod.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
}

variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "state_bucket_name" {
  description = "Nombre globalmente único del bucket de estado, p. ej. stockassistant-tfstate-<cuenta>."
  type        = string
}

variable "github_repository" {
  type    = string
  default = "dgscoppmnd/StockAssistant-Jupiter"
}

variable "github_environment" {
  description = "Entorno GitHub autorizado por OIDC. Restringir sus deployment branches a master en GitHub."
  type        = string
  default     = "production"
}

variable "create_github_oidc_provider" {
  description = "false si la cuenta ya tiene el proveedor token.actions.githubusercontent.com."
  type        = bool
  default     = true
}

variable "deploy_role_policy_arns" {
  description = "Políticas gestionadas extra para el rol de despliegue. Por defecto ninguna: se usa la política mínima de este fichero."
  type        = list(string)
  default     = []
}

variable "ecr_repository_name" {
  type    = string
  default = "stockassistant-api"
}

variable "api_function_name" {
  type    = string
  default = "stockassistant-api"
}

variable "frontend_bucket_name" {
  description = "Bucket del front. Vacío = frontend-<cuenta>-<región>-an."
  type        = string
  default     = ""
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "StockAssistant"
      ManagedBy = "terraform"
      Stack     = "bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "tfstate" {
  bucket = var.state_bucket_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  github_oidc_provider_arn = (
    var.create_github_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
  )
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "stockassistant-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

resource "aws_iam_role_policy_attachment" "github_deploy" {
  for_each   = toset(var.deploy_role_policy_arns)
  role       = aws_iam_role.github_deploy.name
  policy_arn = each.value
}

locals {
  account_id      = data.aws_caller_identity.current.account_id
  frontend_bucket = var.frontend_bucket_name != "" ? var.frontend_bucket_name : "frontend-${local.account_id}-${var.region}-an"
}

# Mínimo privilegio: solo lo que necesita el workflow de despliegue (no ejecuta Terraform).
data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = ["arn:aws:ecr:${var.region}:${local.account_id}:repository/${var.ecr_repository_name}"]
  }

  statement {
    sid = "LambdaDeploy"
    actions = [
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:UpdateFunctionCode",
    ]
    resources = ["arn:aws:lambda:${var.region}:${local.account_id}:function:${var.api_function_name}"]
  }

  statement {
    sid       = "FrontendList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.frontend_bucket}"]
  }

  statement {
    sid       = "FrontendSync"
    actions   = ["s3:DeleteObject", "s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::${local.frontend_bucket}/*"]
  }

  statement {
    sid       = "CloudFrontInvalidate"
    actions   = ["cloudfront:CreateInvalidation", "cloudfront:GetDistribution", "cloudfront:ListDistributions"]
    resources = ["*"]
  }

  statement {
    sid       = "BuildTimeConfig"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/stockassistant/prod/google_client_id"]
  }

  statement {
    sid       = "DatabaseMigrationCredential"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/stockassistant/prod/db/migrator_password"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "deploy-app"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}

output "github_deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}
