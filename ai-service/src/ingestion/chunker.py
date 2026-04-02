import hashlib
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .constants import SECTION_PATTERN


class DocumentChunker:
    def _split_legal_sections(self, text: str) -> list[str]:
        matches = list(SECTION_PATTERN.finditer(text))
        if not matches:
            return [text]
        sections = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section = text[start:end].strip()
            if section:
                sections.append(section)
        return sections

    def _classify_clause_metadata(self, text: str) -> dict:
        t = text.lower()
        metadata = {}

        match = re.search(r"^(\d+(\.\d+)*)[.:\s]+(.+)", text, re.MULTILINE)
        if match:
            metadata["clause_number"] = match.group(1)
            metadata["clause_title"] = match.group(3)[:100]
            metadata["clause_path"] = match.group(1)
        else:
            h = int(hashlib.sha256(text[:50].encode()).hexdigest(), 16) % 10000
            metadata["clause_path"] = f"section_{h}"

        if "payment" in t or "fee" in t or "pricing" in t:
            metadata.update({"clause_type": "Payment", "importance": 3})
        elif "terminate" in t or "cancellation" in t:
            metadata.update({"clause_type": "Termination", "importance": 3})
        elif "liability" in t or "indemn" in t or "warranty" in t:
            metadata.update({"clause_type": "Liability", "importance": 3})
        elif "confidential" in t or "nda" in t or "intellectual property" in t:
            metadata.update({"clause_type": "Confidentiality", "importance": 2})
        elif "insurance" in t or "exhibit" in t or "schedule" in t or "notices" in t:
            metadata.update({"clause_type": "Administrative", "importance": 1})
        elif "define" in t or "definition" in t or "meaning" in t:
            metadata.update({"clause_type": "Definition", "importance": 2})
        else:
            metadata.update({"clause_type": "General", "importance": 1})

        return metadata

    def chunk_document(self, text: str, document_id: str) -> list[Document]:
        # Called via asyncio.to_thread — contextvars don't cross thread
        # boundaries so update_observation is a no-op here. Timing is
        # captured in process_document() and written to the trace there.
        chunks = []
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)

        for section in self._split_legal_sections(text):
            clause_meta = self._classify_clause_metadata(section)
            section_chunks = [section] if len(section) < 2000 else splitter.split_text(section)

            for i, chunk_text in enumerate(section_chunks):
                chunk_id = hashlib.sha256(
                    f"{document_id}_{clause_meta['clause_path']}_{i}_{chunk_text[:50]}".encode()
                ).hexdigest()

                chunks.append(Document(
                    page_content=chunk_text,
                    metadata={
                        "document_id": document_id,
                        "chunk_index": i,
                        "chunk_id": chunk_id,
                        **clause_meta,
                    },
                ))

        return chunks
