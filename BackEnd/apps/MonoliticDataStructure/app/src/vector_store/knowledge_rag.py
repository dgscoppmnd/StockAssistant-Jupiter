from pathlib import Path
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import re
import os

CURRENT_FILE = Path(__file__).resolve()

# Apunta a la carpeta de datos
BASE_DIR = Path(__file__).resolve().parent.parent.parent

KNOWLEDGE_DIR = BASE_DIR / "BackEnd/apps/MonoliticDataStructure/app/data/knowledge"

# Configuración de Ollama y Qdrant
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# URL de Qdrant (por defecto en Docker)
QDRANT_URL = os.getenv("QDRANT_URL", "http://host.docker.internal:6333")
COLLECTION_NAME = "RAG-Documentation-Qdrant"

# Asegurar directorios locales si usas almacenamiento local de archivos
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)




def infer_zone(content: str) -> str:
    content_lower = content.lower()
    
    zones_keywords = {
        "analiticas": ["analítica", "analiticas", "dashboard", "informe", "tendencia", "kpi", "métrica", "metrica"],
        "metricas": ["rendimiento", "desempeño", "conversión", "porcentaje", "tasa"],
        "logistica": ["logística", "logistica", "envío", "envio", "transporte", "distribución"],
        "inventario": ["inventario", "stock", "existencias", "almacenamiento", "restock", "reabastecimiento", "rotación", "mínimo requerido", "sku"],
        "producto": ["catálogo", "catalogo", "categoría"], 
        "ventas": ["facturación", "ingreso neto", "orden de compra", "transacción"],
        "proveedores": ["proveedor", "proveedores", "suministro", "abastecimiento"],
    }

    zone_scores = {}
    for zone, keywords in zones_keywords.items():
        score = 0
        for kw in keywords:
            matches = len(re.findall(rf"\b{re.escape(kw)}\b", content_lower))
            score += matches
        if score > 0:
            zone_scores[zone] = score

    if not zone_scores:
        return "general"

    sorted_zones = sorted(zone_scores.items(), key=lambda x: x[1], reverse=True)
    best_zone, best_score = sorted_zones[0]

    if best_score < 2:
        return "general"

    
    if len(sorted_zones) > 1:
        second_zone, second_score = sorted_zones[1]
        if (best_score - second_score < 2) and best_score < 5:
            return "general"

    return best_zone


from langchain_core.documents import Document

def load_internal_documents(data_dir: Path = KNOWLEDGE_DIR) -> list:
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"El directorio de conocimiento no existe: {data_dir}")

    documents = []
    for document in data_dir.glob("*"):
        if not document.is_file():
            continue
        ext = document.suffix.lower()
        try:
            docs = []
            if ext in [".md", ".txt"]:
                content = document.read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    docs = [Document(page_content=content, metadata={})]
            elif ext == ".pdf":
                docs = PyPDFLoader(str(document)).load()
            else:
                continue

            # 1. Inferimos la zona analizando TODO el contenido del archivo de forma automática
            full_text = " ".join([d.page_content for d in docs])
            file_zone = infer_zone(full_text)

            # 2. Asignamos la zona detectada a los metadatos del documento base
            for d in docs:
                d.metadata["source_name"] = document.name
                d.metadata["source_type"] = ext.lstrip(".")
                d.metadata["zone"] = file_zone  # Heredado de todo el archivo automáticamente
            
            if docs:
                documents.extend(docs)
                print(f"✅ Archivo procesado | {document.name} -> Zona detectada: '{file_zone}'")
        except Exception as e:
            print(f"❌ Error procesando {document.name}: {e}")

    if not documents:
        raise FileNotFoundError(f"No se pudieron cargar documentos válidos en {data_dir}")
    return documents


def get_vectorstore() -> QdrantVectorStore:
    """Conecta o inicializa Qdrant con los embeddings de Ollama."""
    embeddings = OllamaEmbeddings(
        model=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL
    )

    client = QdrantClient(url=QDRANT_URL)

    collections = [col.name for col in client.get_collections().collections]

    if COLLECTION_NAME in collections:
        print(f"Cargando colección existente '{COLLECTION_NAME}' desde Qdrant...")
        return QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=embeddings,
        )

    print(f"Indexando documentos por primera vez en Qdrant ({COLLECTION_NAME})...")
    documents = load_internal_documents(KNOWLEDGE_DIR)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=120,
        add_start_index=True,
    )

    guide_splits = text_splitter.split_documents(documents)
    
    
    # Crear la colección e insertar los documentos en Qdrant
    vector_store = QdrantVectorStore.from_documents(
        documents=guide_splits,
        embedding=embeddings,
        url=QDRANT_URL,
        collection_name=COLLECTION_NAME,
    )

    return vector_store


def format_docs(docs):
    return "\n\n".join(
        f"[Fuente: {doc.metadata.get('source_name', 'Desconocido')} | Zona: {doc.metadata.get('zone', 'general')}]\n{doc.page_content}"
        for doc in docs
    )


def ask_rag(query: str, top_k: int = 3, target_zone: str = None) -> str:
    """
    Realiza la búsqueda en Qdrant aplicando un filtro por zona (metadatos)
    y genera una respuesta usando Ollama local.
    """
    vectorstore = get_vectorstore()

    # Si no se pasa una zona por argumento, la inferimos automáticamente de la pregunta
    zone_to_filter = target_zone if target_zone else infer_zone(query)
    
    search_kwargs = {"k": top_k}
    
    # Aplicar filtro en Qdrant usando 'metadata.zone' (ruta correcta en langchain-qdrant)
    if zone_to_filter and zone_to_filter != "general":
        print(f"Aplicando filtro Qdrant nativo -> metadata.zone: '{zone_to_filter}'")
        search_kwargs["filter"] = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.zone",
                    match=models.MatchValue(value=zone_to_filter),
                )
            ]
        )
    else:
        print("Búsqueda global (sin filtro de zona estricto).")

    retriever = vectorstore.as_retriever(
        search_type="similarity", 
        search_kwargs=search_kwargs
    )

    

    llm = ChatOllama(
        model=OLLAMA_CHAT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2
    )

    template = """Eres un asistente virtual experto del proyecto StockAssistant-Jupiter. 
Responde a la pregunta utilizando únicamente el siguiente contexto extraído de la documentación técnica.
Si no sabes la respuesta basándote en el contexto, di claramente "No dispongo de suficiente información en la documentación para responder esa pregunta".

Contexto:
{context}

Pregunta: {question}

Respuesta:"""

    prompt = ChatPromptTemplate.from_template(template)

    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain.invoke(query)