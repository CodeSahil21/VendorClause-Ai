# Standard library
import hashlib
import re

# Third-party
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Local
from .constants import SECTION_PATTERN


class DocumentChunker:
    def _leading_clause_number(self, section: str) -> str | None:
        match = re.match(r"^\s*(\d+(?:\.\d+)+)", section)
        return match.group(1) if match else None

    def _leading_letter(self, section: str) -> str | None:
        """Return the leading letter label (a-z) if section starts with 'a.', 'b.' etc."""
        match = re.match(r"^\s*([a-z])\.\.?\s", section)
        return match.group(1) if match else None

    def _subsection_parent(self, clause_number: str | None) -> str | None:
        if not clause_number:
            return None
        parts = clause_number.split(".")
        if len(parts) < 3:
            return None
        return ".".join(parts[:2])

    def _merge_subsections(self, sections: list[str]) -> list[str]:
        if not sections:
            return sections

        merged: list[str] = []
        for section in sections:
            clause_number = self._leading_clause_number(section)
            parent = self._subsection_parent(clause_number)
            letter = self._leading_letter(section)

            if not merged:
                merged.append(section)
                continue

            prev_clause = self._leading_clause_number(merged[-1])
            prev_parent = self._subsection_parent(prev_clause)
            prev_letter = self._leading_letter(merged[-1])

            # Merge numbered subsections: 3.6.1, 3.6.2 → merge into 3.6
            should_merge_numbered = bool(parent) and (
                prev_clause == parent
                or prev_parent == parent
            )

            # Merge lettered subsections: a., b., c. → merge together
            # Only merge if previous section also starts with a letter
            # (keeps lettered items within the same exhibit/list together)
            should_merge_lettered = (
                bool(letter)
                and bool(prev_letter)
                and letter != prev_letter
            )

            if should_merge_numbered or should_merge_lettered:
                merged[-1] = f"{merged[-1]}\n\n{section}"
            else:
                merged.append(section)

        return merged

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
        return self._merge_subsections(sections)

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

        # Order matters: apply specific legal clause signals before broader terms.
        if "indemn" in t:
            metadata.update({"clause_type": "Indemnification", "importance": 3})
        elif "terminat" in t or "cancell" in t or (
            "expir" in t
            and ("agreement" in t or "contract" in t or "term" in t)
            and "payment" not in t
            and "invoice" not in t
            and "insurance" not in t
            and "policy" not in t
            and "coverage" not in t
            and "certificate" not in t
            and "renewal" not in t
        ):
            metadata.update({"clause_type": "Termination", "importance": 3})
        elif "payment" in t or "invoice" in t or "compensation" in t or "pricing" in t:
            metadata.update({"clause_type": "Payment", "importance": 3})
        elif "liability" in t or "limitation of liability" in t:
            metadata.update({"clause_type": "Liability", "importance": 3})
        elif re.search(r"\bwarrant", t) or re.search(r"\brepresent(?:ation|s)?\b", t) or "guarantee" in t:
            metadata.update({"clause_type": "Warranty", "importance": 3})
        elif "insurance" in t or "coverage" in t or "liability limit" in t or "exhibit d" in t:
            metadata.update({"clause_type": "Insurance", "importance": 3})
        elif "confidential" in t or "nda" in t or "proprietary" in t:
            metadata.update({"clause_type": "Confidentiality", "importance": 2})
        elif "intellectual property" in t or "copyright" in t or "patent" in t or "work for hire" in t:
            metadata.update({"clause_type": "IPOwnership", "importance": 2})
        elif "arbitrat" in t or "dispute" in t or "governing law" in t or (
            "jurisdiction" in t and ("court" in t or "venue" in t or "arbitrat" in t)
        ):
            metadata.update({"clause_type": "DisputeResolution", "importance": 2})
        elif "force majeure" in t:
            metadata.update({"clause_type": "ForceMajeure", "importance": 2})
        elif re.search(r"\bassign(?:ment|ee|or)?\b", t) or "subcontract" in t:
            metadata.update({"clause_type": "Assignment", "importance": 2})
        elif "defin" in t or "meaning" in t:
            metadata.update({"clause_type": "Definition", "importance": 2})
        elif "exhibit" in t or "schedule" in t or ("notice" in t and "section 11.7" in t):
            metadata.update({"clause_type": "Administrative", "importance": 1})
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
            if len(section.strip()) < 50:
                continue
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
