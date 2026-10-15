variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "vector_bucket_name" {
  description = "Nombre del vector bucket de S3 Vectors (único por cuenta y región)."
  type        = string
  default     = "stockassistant-vectors"
}

variable "embedding_dimension" {
  description = "Dimensión de text-embedding-3-small por defecto. Si usas el parámetro dimensions de OpenAI, iguala este valor."
  type        = number
  default     = 1536
}

variable "frontend_bucket_name" {
  description = "Bucket S3 existente con el build de Vite (se gestiona su política, no su creación)."
  type        = string
  default     = "frontend-118645514410-eu-west-1-an"
}

variable "api_function_name" {
  description = "Lambda con Function URL que atiende /api/*."
  type        = string
  default     = "stockassistant-api"
}

variable "vector_indexes" {
  description = "Índices que sustituyen a las colecciones Qdrant: products y documents."
  type        = set(string)
  default     = ["products", "documents"]
}
