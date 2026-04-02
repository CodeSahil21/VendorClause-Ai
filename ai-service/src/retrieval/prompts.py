"""Legal RAG prompt templates for the retrieval pipeline."""

SUPERVISOR_PROMPT = """You are the supervisor and router for a legal retrieval pipeline.

Classify the user question and produce strict JSON with this shape:
{
  "intent": "factual|comparison|risk|obligation|definition|summarization",
  "clause_types": ["..."],
  "entities": ["..."],
  "strategy": "vector_only|hybrid|graph_only",
  "reason": "short reason"
}

Rules:
- intent must be one of the allowed values.
- strategy must be one of vector_only, hybrid, graph_only.
- prefer graph_only when relationship traversal is clearly required.
- prefer hybrid for complex legal questions spanning entities + clauses.
- return valid JSON only, with no markdown.

User context from mem0:
{mem0_context}

Chat history:
{chat_history}

Question:
{question}
"""


REWRITER_PROMPT = """Rewrite the legal question for retrieval quality.

Rules:
- resolve pronouns using chat history.
- expand legal abbreviations when useful.
- add high-value synonyms without changing meaning.
- keep concise (max 50 words).
- output only the rewritten query text.

Chat history:
{chat_history}

Original question:
{question}
"""


DECOMPOSER_PROMPT = """Decompose the legal question into 2-4 independent sub-queries.

Rules:
- each sub-query must stand alone.
- preserve legal meaning and scope.
- avoid overlap between sub-queries.
- output strict JSON array of strings only.

Question:
{question}
"""


CRAG_EVALUATOR_PROMPT = """You are a retrieval quality evaluator.

Given a user question and retrieved context, decide whether the context is sufficient to answer faithfully.

Return strict JSON:
{
  "context_sufficient": true/false,
  "reason": "short reason",
  "missing_aspects": ["..."]
}

Question:
{question}

Retrieved context:
{context}
"""


GENERATOR_PROMPT = """Answer the legal question using only the provided context.

Rules:
- do not invent facts.
- include explicit citations with chunk ids in the form [chunk_id:...].
- if context is insufficient, say so clearly.
- keep legal language precise and concise.

Question:
{question}

Context chunks:
{context}

Response:
"""


HALLUCINATION_CHECKER_PROMPT = """You are a legal faithfulness checker.

Validate whether the generated answer is fully grounded in the context.

Return strict JSON:
{
  "is_faithful": true/false,
  "issues": ["..."],
  "confidence": 0.0
}

Question:
{question}

Context:
{context}

Generated answer:
{answer}
"""


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


RESPONSE_GENERATION_PROMPT = """You are a legal contract analysis assistant. Answer the user's question based ONLY on the provided context. Cite sources using [Page X, Clause Y] format.

Rules:
- Answer ONLY from the provided context and never fabricate information
- If the context does not contain the answer, say "I could not find this information in the uploaded documents."
- Use precise legal language
- When referencing specific provisions, cite clause number and page
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


RESPONSE_REFINEMENT_PROMPT = """You are a legal accuracy editor. The initial answer had factual issues when checked against the source context. Rewrite the answer to fix these problems.

Issues found:
{issues}

Source context:
{context}

Original answer:
{answer}

User question: {question}

Corrected answer:"""


# Compatibility aliases for older naming.
RETRIEVAL_ANALYSIS_PROMPT = SUPERVISOR_PROMPT
RETRIEVAL_REWRITE_PROMPT = REWRITER_PROMPT
RETRIEVAL_DECOMPOSITION_PROMPT = DECOMPOSER_PROMPT

QUERY_ANALYSIS_PROMPT = SUPERVISOR_PROMPT
QUERY_REWRITE_PROMPT = REWRITER_PROMPT
QUERY_DECOMPOSITION_PROMPT = DECOMPOSER_PROMPT
