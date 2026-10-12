variable "documents_bucket_name" {
  description = "Bucket privado para documentos del RAG e imágenes de producto"
  type        = string
  default     = "stockassistant-files-118645514410-eu-west-1"
}

resource "aws_s3_bucket" "files" {
  bucket = var.documents_bucket_name
}

resource "aws_s3_bucket_public_access_block" "files" {
  bucket                  = aws_s3_bucket.files.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "files" {
  bucket = aws_s3_bucket.files.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

output "documents_bucket" {
  value = aws_s3_bucket.files.bucket
}
