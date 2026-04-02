import re

GRAPH_SYSTEM_PROMPT = """
Extract a COMPLETE legal knowledge graph from the given text. Do not miss any crucial legal entity, definition, or relationship.

Rules:
- Allowed node types: Party, Clause, Obligation, Right, Payment, Service, TerminationCondition, Liability, ConfidentialInformation, Date, Jurisdiction, Definition, Regulation, Asset.
- Allowed relationship types: HAS_CLAUSE, HAS_OBLIGATION, OWES_PAYMENT, PROVIDES_SERVICE, CAN_TERMINATE, LIMITS_LIABILITY, GOVERNS, EFFECTIVE_ON, DEFINES, COMPLIES_WITH, APPLIES_TO.
- Extract node properties where applicable (e.g., specific amounts, dates, specific conditions, or exact definitions).
- Normalize entity names to be consistent (e.g., "Service Provider" -> "provider", "Client" -> "customer").
- Avoid generic words as standalone nodes.
Return ONLY valid JSON.
"""

ALLOWED_NODES = {
    "Party", "Clause", "Obligation", "Right", "Payment",
    "Service", "TerminationCondition", "Liability",
    "ConfidentialInformation", "Date", "Jurisdiction",
    "Definition", "Regulation", "Asset",
}

ALLOWED_RELATIONSHIPS = {
    "HAS_CLAUSE", "HAS_OBLIGATION", "OWES_PAYMENT",
    "PROVIDES_SERVICE", "CAN_TERMINATE", "LIMITS_LIABILITY",
    "GOVERNS", "EFFECTIVE_ON", "DEFINES", "COMPLIES_WITH", "APPLIES_TO",
}

ENTITY_ALIASES = {
    "service provider": "provider",
    "vendor": "provider",
    "supplier": "provider",
    "client": "customer",
    "customer": "customer",
    "buyer": "customer",
    "purchaser": "customer",
    "company": "company",
}

IGNORED_ENTITIES = {"agreement", "contract", "this agreement", "herein", "hereto"}

SECTION_PATTERN = re.compile(
    r"(\d+\.\s+[A-Z][A-Z\s]+|\d+(\.\d+)*|§\d+|Section\s+\d+|Article\s+[IVX]+)",
    re.VERBOSE | re.IGNORECASE,
)
