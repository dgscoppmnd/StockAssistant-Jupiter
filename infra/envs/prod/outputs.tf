output "vector_bucket_name" {
  value = aws_s3vectors_vector_bucket.main.vector_bucket_name
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "vector_index_arns" {
  value = { for name, index in aws_s3vectors_index.main : name => index.index_arn }
}
