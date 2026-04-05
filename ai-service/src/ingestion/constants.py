import re

GRAPH_SYSTEM_PROMPT = """
Extract a COMPLETE legal knowledge graph from the given contract text.

Rules:
- Allowed node types: Party, Clause, Obligation, Right, Payment, Service, TerminationCondition, Liability, ConfidentialInformation, Date, Jurisdiction, Definition, Regulation, Asset.
- Allowed relationship types: HAS_CLAUSE, HAS_OBLIGATION, OWES_PAYMENT, PROVIDES_SERVICE, CAN_TERMINATE, LIMITS_LIABILITY, GOVERNS, EFFECTIVE_ON, DEFINES, COMPLIES_WITH, APPLIES_TO.
- Always extract numeric values, timeframes, and dollar amounts as node properties.
- Always extract party full names and roles as node properties.
- Extract section references as Clause nodes with section number and topic as properties.
- Normalize party names: "Service Provider"/"Vendor"/"Supplier" -> "vendor"; "Client"/"Customer"/"Buyer" -> "customer".
- Avoid generic/boilerplate words as standalone nodes.
- Each relationship must link two specific named nodes.
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
    "supplier": "provider",
    "the vendor": "vendor",
    "client": "customer",
    "the client": "customer",
    "customer": "customer",
    "buyer": "customer",
    "purchaser": "customer",
    "company": "company",
}

IGNORED_ENTITIES = {"herein", "hereto", "thereof", "therein", "thereto", "hereby", "hereunder", "whereof"}

SECTION_PATTERN = re.compile(
    r"^(\d+(\.\d+)*[.:\s]|§\s*\d+|Section\s+\d+(\.\d+)*|SECTION\s+\d+|Article\s+[IVX]+|ARTICLE\s+\d+|[A-Z]\.\s+|\([a-z]\)\s+|\([ivx]+\)\s+)",
    re.MULTILINE | re.IGNORECASE,
)
