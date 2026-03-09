"""
Legal RAG Prompt Templates

All prompts used across the query pipeline:
- Query analysis (classification + routing)
- Query rewriting (expansion + decomposition)
- Response generation (with citations)
- Hallucination grading
"""

# ──────────────────────────────────────────────
# 1. QUERY ANALYSIS — Classify intent & route
# ──────────────────────────────────────────────

QUERY_ANALYSIS_PROMPT = """You are a legal document query analyzer. Analyze the user's question and produce a JSON object with these fields:

1. "intent": one of ["factual", "comparison", "summarization", "obligation", "risk_analysis", "definition"]
   - factual: asks about a specific fact, clause, or value (e.g. "What is the termination notice period?")
   - comparison: compares two clauses or provisions (e.g. "How does liability differ from indemnification?")
   - summarization: asks for a summary of a section or the whole document
   - obligation: asks what a party must do (e.g. "What are the vendor's obligations?")
   - risk_analysis: asks about risks, penalties, or exposure
   - definition: asks what a term means

2. "clause_types": list of relevant clause types from ["PaymentTerm", "Termination", "Confidentiality", "Indemnification", "Insurance", "IPOwnership", "DisputeResolution", "Warranty", "ServiceLevel", "General"]

3. "entities": list of party names or legal entities mentioned

4. "requires_graph": boolean — true if the question involves relationships between parties/clauses (e.g. "Who owes what to whom?")

5. "search_strategy": one of ["vector_only", "graph_only", "hybrid"]
   - vector_only: simple factual lookups
   - graph_only: relationship/entity queries
   - hybrid: complex questions needing both

User question: {question}

Chat history (last 3 turns):
{chat_history}

Respond ONLY with valid JSON, no explanation."""


# ──────────────────────────────────────────────
# 2. QUERY REWRITING — Expand & disambiguate
# ──────────────────────────────────────────────

QUERY_REWRITE_PROMPT = """You are a legal query optimizer. Given the user's original question and conversation context, rewrite it into a better search query.

Rules:
- Resolve pronouns using chat history (e.g. "it" → "the confidentiality clause")
- Expand legal abbreviations (e.g. "IP" → "intellectual property", "SLA" → "service level agreement")
- Add relevant legal synonyms (e.g. "terminate" → "terminate OR cancel OR rescind")
- Keep the rewrite concise (under 50 words)
- Do NOT change the meaning or add information not implied by the question

Original question: {question}
Chat history: {chat_history}

Rewritten query:"""


# ──────────────────────────────────────────────
# 3. MULTI-QUERY DECOMPOSITION — For complex questions
# ──────────────────────────────────────────────

QUERY_DECOMPOSITION_PROMPT = """You are a legal research assistant. The user asked a complex question that requires multiple lookups. Break it into 2-4 simpler sub-questions that can each be answered independently.

Rules:
- Each sub-question should target a specific clause type or entity
- Keep sub-questions self-contained (no pronouns referring to other sub-questions)
- Preserve the legal precision of the original question

Original question: {question}

Return a JSON array of sub-questions:
["sub-question 1", "sub-question 2", ...]"""


# ──────────────────────────────────────────────
# 4. NEO4J CYPHER GENERATION — Graph queries
# ──────────────────────────────────────────────

CYPHER_GENERATION_PROMPT = """You are a Neo4j Cypher query generator for a legal contract knowledge graph.

The graph schema:
- Node labels: Entity (with properties: id, type, document_id, confidence)
  - Entity types: Party, Contract, Clause, Obligation, Liability, PaymentTerm, Termination, Confidentiality, ServiceLevel
- Relationship type: RELATES (with properties: type, document_id, confidence)
  - Relationship types stored in 'type' property: HAS_CLAUSE, OWES_OBLIGATION, LIMITS_LIABILITY, TERMINATES, PAYS, PROVIDES_SERVICE
- Document node: Document (with properties: id, doc_type, created_at)

Rules:
- Always use MATCH, never CREATE/DELETE/SET
- Filter by document_id when provided: $document_id
- Limit results to 20
- Return meaningful aliases

User question: {question}
Document ID filter: {document_id}

Cypher query:"""


# ──────────────────────────────────────────────
# 5. RESPONSE GENERATION — Final answer with citations
# ──────────────────────────────────────────────

RESPONSE_GENERATION_PROMPT = """You are a legal contract analysis assistant. Answer the user's question based ONLY on the provided context. Cite sources using [Page X, Clause Y] format.

Rules:
- Answer ONLY from the provided context — never fabricate information
- If the context does not contain the answer, say "I could not find this information in the uploaded documents."
- Use precise legal language
- When referencing specific provisions, cite the clause number and page
- For obligations, clearly state which party is obligated
- For monetary values or deadlines, quote them exactly
- Structure complex answers with bullet points

Context from vector search:
{vector_context}

Context from knowledge graph:
{graph_context}

Chat history:
{chat_history}

User question: {question}

Answer:"""


# ──────────────────────────────────────────────
# 6. HALLUCINATION GRADING — Verify faithfulness
# ──────────────────────────────────────────────

HALLUCINATION_GRADE_PROMPT = """You are a legal accuracy checker. Given a generated answer and the source context it was derived from, determine if the answer is faithful to the sources.

Check for:
1. Claims not supported by any source chunk
2. Misquoted values (amounts, dates, percentages)
3. Attributed obligations to the wrong party
4. Invented clause numbers or section references

Source context:
{context}

Generated answer:
{answer}

Respond with JSON:
{{
  "is_faithful": true/false,
  "confidence": 0.0-1.0,
  "issues": ["list of specific problems found, or empty"]
}}"""


# ──────────────────────────────────────────────
# 7. RESPONSE REFINEMENT — Fix hallucination issues
# ──────────────────────────────────────────────

RESPONSE_REFINEMENT_PROMPT = """You are a legal accuracy editor. The initial answer had factual issues when checked against the source context. Rewrite the answer to fix these problems.

Issues found:
{issues}

Source context:
{context}

Original answer:
{answer}

User question: {question}

Corrected answer:"""
