from pathlib import Path
from langchain_chroma import Chroma
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
CHROMA_GUIDE_DIR = BASE_DIR / "BackEnd/apps/MonoliticDataStructure/app/data/chroma_db_ollama"

# Asegurar directorios
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_GUIDE_DIR.mkdir(parents=True, exist_ok=True)

# Configuración de Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")         # Usado para redactar respuestas
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text") # Usado para generar embeddings


def infer_zone(content: str) -> str:
    content_lower = content.lower()
    zones_keywords = {
        "analiticas": ["analítica", "analiticas", "dashboard", "informe", "tendencia", "kpi", "métrica", "metrica"],
        "metricas": ["métrica", "metrica", "métricas", "metricas", "rendimiento", "desempeño", "conversión", "porcentaje", "tasa"],
        "logistica": ["logística", "logistica", "envío", "envio", "transporte", "almacén", "almacen", "distribución"],
        "inventario": ["inventario", "stock", "existencias", "almacenamiento", "restock", "reabastecimiento", "rotación"],
        "producto": ["producto", "productos", "sku", "catálogo", "catalogo", "categoría", "artículo"],
        "ventas": ["venta", "ventas", "facturación", "ingreso", "orden", "pedido", "cliente", "transacción"],
        "proveedores": ["proveedor", "proveedores", "compras", "suministro", "abastecimiento"],
    }

    zone_counts = {}
    for zone, keywords in zones_keywords.items():
        count = 0
        for kw in keywords:
            count += len(re.findall(rf"\b{re.escape(kw)}\b", content_lower))
        if count > 0:
            zone_counts[zone] = count

    if zone_counts:
        return max(zone_counts, key=zone_counts.get)
    return "general"


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
            if ext in [".md", ".txt"]:
                docs = TextLoader(str(document), encoding="utf-8").load()
            elif ext == ".pdf":
                docs = PyPDFLoader(str(document)).load()
            else:
                continue

            for d in docs:
                d.metadata["source_name"] = document.name
                d.metadata["source_type"] = ext.lstrip(".")
                d.metadata["zone"] = infer_zone(d.page_content)
            documents.extend(docs)
        except Exception as e:
            print(f"Error procesando {document.name}: {e}")

    if not documents:
        raise FileNotFoundError(f"No se encontraron documentos en {data_dir}")
    return documents


def get_or_create_vectorstore() -> Chroma:
    # Usar explícitamente el modelo especializado de embeddings en local
    embeddings = OllamaEmbeddings(
        model=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL
    )

    if CHROMA_GUIDE_DIR.exists() and any(CHROMA_GUIDE_DIR.iterdir()):
        print("Cargando VectorStore existente de ChromaDB (Ollama)...")
        return Chroma(
            persist_directory=str(CHROMA_GUIDE_DIR),
            embedding_function=embeddings,
            collection_name="RAG-Documentation-Ollama",
        )

    print("Indexando documentos por primera vez con Ollama...")
    documents = load_internal_documents(KNOWLEDGE_DIR)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=120,
        add_start_index=True,
    )

    guide_splits = text_splitter.split_documents(documents)
    for i, d in enumerate(guide_splits):
        d.metadata["chunk_id"] = i
        d.metadata.setdefault("zone", infer_zone(d.page_content))

    guide_store = Chroma.from_documents(
        documents=guide_splits,
        embedding=embeddings,
        persist_directory=str(CHROMA_GUIDE_DIR),
        collection_name="RAG-Documentation-Ollama",
    )

    return guide_store


def format_docs(docs):
    return "\n\n".join(
        f"[Fuente: {doc.metadata.get('source_name', 'Desconocido')}]\n{doc.page_content}"
        for doc in docs
    )


def ask_rag(query: str, top_k: int = 3) -> str:
    """Realiza la búsqueda en ChromaDB y genera una respuesta usando Ollama local."""
    vectorstore = get_or_create_vectorstore()

    retriever = vectorstore.as_retriever(
        search_type="similarity", search_kwargs={"k": top_k}
    )

    # LLM local para generar respuestas
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