import io
import uuid
import logging
import threading
from sqlalchemy.orm import Session
from pypdf import PdfReader
import chromadb
from app.config import settings
from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)

class RAGService:
    _chroma_client = None
    _collection = None
    _init_lock = threading.Lock()

    def __init__(self):
        self.chroma_client = None
        self.collection = None
        self.collection_name = "lore_chunks_local"
        self._init_chroma()

    def _init_chroma(self):
        """Initialize ChromaDB client and retrieve/create the local lore collection with Cosine distance."""
        if RAGService._chroma_client is not None and RAGService._collection is not None:
            self.chroma_client = RAGService._chroma_client
            self.collection = RAGService._collection
            return

        with RAGService._init_lock:
            if RAGService._chroma_client is not None and RAGService._collection is not None:
                self.chroma_client = RAGService._chroma_client
                self.collection = RAGService._collection
                return

            try:
                chroma_client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT
                )
                collection = chroma_client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"Successfully connected to ChromaDB server. Collection: {self.collection_name}")
            except Exception as e:
                logger.error(f"Failed to connect to ChromaDB server: {e}. Attempting local persistent client...")
                try:
                    # Fallback for local dev/testing outside Docker
                    chroma_client = chromadb.PersistentClient(path="./chroma_db_local")
                    collection = chroma_client.get_or_create_collection(
                        name=self.collection_name,
                        metadata={"hnsw:space": "cosine"}
                    )
                    logger.info(f"ChromaDB local persistent fallback initialized. Collection: {self.collection_name}")
                except Exception as le:
                    logger.critical(f"ChromaDB completely unavailable: {le}")
                    return

            RAGService._chroma_client = chroma_client
            RAGService._collection = collection
            self.chroma_client = chroma_client
            self.collection = collection


    def extract_text(self, file_bytes: bytes, file_name: str, content_type: str) -> str:
        """Extract plain text from TXT, MD, or PDF files."""
        content_type = content_type.lower()
        if "pdf" in content_type or file_name.endswith(".pdf"):
            try:
                pdf_file = io.BytesIO(file_bytes)
                reader = PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text
            except Exception as e:
                logger.error(f"Failed to extract text from PDF: {e}")
                raise ValueError(f"Could not parse PDF file: {e}")
        else:
            # Assume plain text/markdown
            try:
                return file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    return file_bytes.decode("latin-1")
                except Exception as e:
                    logger.error(f"Failed to decode text file: {e}")
                    raise ValueError("Could not decode text file. Ensure it is UTF-8 or Latin-1 encoded.")

    def chunk_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
        """Split text into overlapping chunks, attempting to break on word/newline boundaries."""
        if not text:
            return []
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # Split at whitespace if we're not at the very end
            if end < text_len:
                split_idx = -1
                # Look back up to 100 characters to find a good separator
                for i in range(end, max(end - 100, start), -1):
                    if text[i] in ['\n', ' ']:
                        split_idx = i
                        break
                if split_idx != -1:
                    end = split_idx
            
            chunk_content = text[start:end].strip()
            if chunk_content:
                chunks.append(chunk_content)
            
            # Adjust start for the next iteration (incorporating overlap)
            next_start = end - chunk_overlap
            if next_start <= start:
                # Force forward progress if overlap prevents it
                start = end
            else:
                start = next_start
                
        return chunks

    def process_document(
        self, 
        db: Session, 
        file_name: str, 
        file_bytes: bytes, 
        content_type: str,
        game_project_id: str = "default_project"
    ) -> Document:
        """Processes document: extracts, chunks, writes to DB, embeds, writes to ChromaDB."""
        # 1. Extract plain text
        raw_text = self.extract_text(file_bytes, file_name, content_type)
        if not raw_text.strip():
            raise ValueError("Extracted text content is empty.")

        # 2. Chunk text
        text_chunks = self.chunk_text(raw_text)
        if not text_chunks:
            raise ValueError("No chunks could be generated from the document.")

        # 3. Create Document entry in DB
        db_doc = Document(
            title=file_name,
            content_type=content_type,
            file_path=None, # For this release we don't save files locally, we process bytes in-memory
            game_project_id=game_project_id
        )
        db.add(db_doc)
        db.flush() # Populate the ID

        # 4. Create DocumentChunk entries in DB & prepare lists for Vector DB
        db_chunks = []
        chroma_ids = []
        chroma_texts = []
        chroma_metadatas = []

        for idx, chunk_text in enumerate(text_chunks):
            chunk_id = uuid.uuid4()
            db_chunk = DocumentChunk(
                id=chunk_id,
                document_id=db_doc.id,
                chunk_index=idx,
                content=chunk_text,
                metadata_json={"title": file_name, "chunk_index": idx}
            )
            db_chunks.append(db_chunk)
            db.add(db_chunk)

            # Metadata for ChromaDB
            chroma_ids.append(str(chunk_id))
            chroma_texts.append(chunk_text)
            chroma_metadatas.append({
                "document_id": str(db_doc.id),
                "title": file_name,
                "chunk_index": idx,
                "game_project_id": game_project_id
            })

        # 5. Save in Vector DB using Chroma's local text embedding path.
        if self.collection:
            try:
                self.collection.add(
                    ids=chroma_ids,
                    documents=chroma_texts,
                    metadatas=chroma_metadatas
                )
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to write to ChromaDB. Transaction rolled back: {e}")
                raise e

        db.commit()
        db.refresh(db_doc)
        return db_doc

    def query_lore(self, query_text: str, limit: int = 5, game_project_id: str = "default_project") -> list[dict]:
        """Queries ChromaDB, maps to source records, returns citation and confidence score."""
        if not self.collection:
            raise ValueError("ChromaDB vector collection is unavailable.")

        # 1. Query ChromaDB
        try:
            collection_count = self.collection.count()
            n_results = limit
            if isinstance(collection_count, (int, float)):
                if collection_count == 0:
                    return []
                n_results = min(limit, int(collection_count))
            
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where={"game_project_id": game_project_id}
            )
        except Exception as e:
            logger.error(f"Failed to query ChromaDB: {e}")
            raise e

        # 2. Format response
        formatted_results = []
        if not results or not results["ids"] or len(results["ids"][0]) == 0:
            return formatted_results

        # Extract items
        ids = results["ids"][0]
        distances = results["distances"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        for i in range(len(ids)):
            distance = distances[i]
            # Since distance space is Cosine:
            # distance ranges from 0.0 (identical) to 2.0.
            # similarity = 1.0 - distance
            similarity = max(0.0, min(1.0, 1.0 - distance))

            # Determine confidence rating
            if similarity >= 0.75:
                confidence = "High"
            elif similarity >= 0.55:
                confidence = "Medium"
            else:
                confidence = "Low"

            formatted_results.append({
                "chunk_id": ids[i],
                "content": documents[i],
                "document_id": metadatas[i].get("document_id"),
                "title": metadatas[i].get("title"),
                "chunk_index": metadatas[i].get("chunk_index"),
                "similarity": round(similarity, 4),
                "confidence": confidence
            })

        return formatted_results

    def backfill_local_collection(self, db: Session):
        """
        Read existing DocumentChunk rows from relational DB and add them
        to the local collection (lore_chunks_local) if they aren't already indexed.
        Uses batching and handles individual chunk indexing failures gracefully.
        """
        if not self.chroma_client:
            logger.warning("Chroma client not initialized. Skipping backfill.")
            return

        try:
            # Always ensure lore_chunks_local is created
            local_collection = self.chroma_client.get_or_create_collection(
                name="lore_chunks_local",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"Failed to retrieve or create lore_chunks_local collection: {e}")
            return

        from app.models.document import DocumentChunk
        # 1. Batch read DocumentChunks from DB to avoid high memory consumption
        chunk_query = db.query(DocumentChunk)
        total_chunks = chunk_query.count()
        if total_chunks == 0:
            logger.info("No DocumentChunks found in SQL database for local backfill.")
            return

        logger.info(f"Starting vector database local backfill check for {total_chunks} chunks...")

        batch_size = 100
        offset = 0
        while offset < total_chunks:
            batch = chunk_query.offset(offset).limit(batch_size).all()
            if not batch:
                break

            # Get list of IDs in this batch
            ids_to_check = [str(chunk.id) for chunk in batch]
            try:
                # Retrieve existing vector records by ID in a single call to avoid duplicates
                existing_res = local_collection.get(ids=ids_to_check, include=[])
                existing_ids = set(existing_res.get("ids", []))
            except Exception as get_err:
                logger.error(f"Error checking existing IDs in local collection: {get_err}")
                existing_ids = set()

            # Filter out chunks that already exist in Chroma
            missing_chunks = [c for c in batch if str(c.id) not in existing_ids]

            if missing_chunks:
                logger.info(f"Backfilling {len(missing_chunks)} chunks to lore_chunks_local (batch offset {offset})...")
                # Add chunks one-by-one or in a sub-batch, handling individual failures gracefully so we do not crash startup
                for chunk in missing_chunks:
                    try:
                        # Fetch associated document title/project
                        doc_title = chunk.document.title if chunk.document else "Untitled"
                        doc_project = chunk.document.game_project_id if chunk.document else "default_project"
                        
                        local_collection.add(
                            ids=[str(chunk.id)],
                            documents=[chunk.content],
                            metadatas=[{
                                "document_id": str(chunk.document_id),
                                "title": doc_title,
                                "chunk_index": chunk.chunk_index,
                                "game_project_id": doc_project
                            }]
                        )
                    except Exception as add_err:
                        logger.error(f"Failed to index individual chunk {chunk.id} in lore_chunks_local: {add_err}")

            offset += batch_size

        logger.info("Vector database local backfill check completed.")
