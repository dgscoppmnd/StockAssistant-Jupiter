resource "aws_s3vectors_vector_bucket" "main" {
  vector_bucket_name = var.vector_bucket_name

  encryption_configuration {
    sse_type = "AES256"
  }
}

# Sin metadata_configuration: todos los metadatos son filtrables.
# Guarda document_id / chunk_id como metadato para sustituir el filtro has_id de Qdrant.
resource "aws_s3vectors_index" "main" {
  for_each = var.vector_indexes

  index_name         = each.key
  vector_bucket_name = aws_s3vectors_vector_bucket.main.vector_bucket_name

  data_type       = "float32"
  dimension       = var.embedding_dimension
  distance_metric = "cosine"
}
