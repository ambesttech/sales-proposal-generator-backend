from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeChunk:
    category: str
    title: str
    body: str
    keywords: tuple[str, ...]


_CHUNKS: list[KnowledgeChunk] = [
    KnowledgeChunk(
        category="service",
        title="Discovery & alignment workshop",
        body=(
            "Facilitated sessions to clarify goals, stakeholders, success metrics, and delivery "
            "constraints. Outputs: prioritized backlog, risk register, and milestone plan."
        ),
        keywords=("discovery", "workshop", "alignment", "stakeholders", "metrics"),
    ),
    KnowledgeChunk(
        category="service",
        title="Custom web application delivery",
        body=(
            "End-to-end delivery for secure, maintainable web apps: UX flows, API design, "
            "implementation, automated testing, observability, and production rollout."
        ),
        keywords=("web", "application", "api", "implementation", "qa"),
    ),
    KnowledgeChunk(
        category="service",
        title="Data integration & automation",
        body=(
            "Connect CRM, billing, and internal tools with reliable pipelines, error handling, "
            "and auditability. Includes monitoring and operational runbooks."
        ),
        keywords=("integration", "crm", "automation", "etl", "billing"),
    ),
    KnowledgeChunk(
        category="case_study",
        title="B2B SaaS onboarding uplift",
        body=(
            "Reduced time-to-value by redesigning onboarding and integrating product analytics. "
            "Result: +18% activation in 90 days without increasing support headcount."
        ),
        keywords=("saas", "onboarding", "analytics", "activation", "b2b"),
    ),
    KnowledgeChunk(
        category="case_study",
        title="Partner portal MVP in 8 weeks",
        body=(
            "Shipped a secure partner portal with role-based access, document exchange, and SLA "
            "tracking. Cut manual coordination hours by roughly 35% for partner managers."
        ),
        keywords=("portal", "partner", "mvp", "roles", "documents"),
    ),
    KnowledgeChunk(
        category="reusable",
        title="Executive summary pattern",
        body=(
            "Lead with business outcome, quantify scope boundaries, name assumptions explicitly, "
            "and close with a crisp decision request and timeline for next steps."
        ),
        keywords=("executive", "summary", "assumptions", "decision"),
    ),
    KnowledgeChunk(
        category="reusable",
        title="Scope phrasing guardrails",
        body=(
            "Prefer phased delivery with exit criteria. Avoid absolute guarantees; use 'target', "
            "'plan', and 'dependent on discovery findings' where uncertainty remains."
        ),
        keywords=("scope", "phased", "guardrails", "language"),
    ),
    KnowledgeChunk(
        category="pricing",
        title="Indicative discovery package",
        body=(
            "Typical discovery engagement: 1–2 weeks calendar time, blended team, fixed-fee range "
            "commonly discussed between $12k and $25k depending on complexity."
        ),
        keywords=("discovery", "fixed-fee", "pricing", "range"),
    ),
    KnowledgeChunk(
        category="pricing",
        title="Implementation banding heuristic",
        body=(
            "For mid-complexity web builds, many proposals land between $45k and $120k depending "
            "on integrations, compliance needs, and SLA expectations. Always confirm after "
            "technical discovery."
        ),
        keywords=("implementation", "budget", "integration", "compliance"),
    ),
]


def _matches(chunk: KnowledgeChunk, needle: str) -> bool:
    n = needle.lower()
    if n in chunk.title.lower() or n in chunk.body.lower():
        return True
    return any(n in k.lower() for k in chunk.keywords)


def search_chunks(needles: list[str], *, limit: int = 14) -> list[KnowledgeChunk]:
    needles = [n.strip() for n in needles if n and len(n.strip()) >= 2][:22]
    if not needles:
        return list(_CHUNKS[:limit])

    out: list[KnowledgeChunk] = []
    for chunk in _CHUNKS:
        if any(_matches(chunk, nd) for nd in needles):
            out.append(chunk)
        if len(out) >= limit:
            break

    if out:
        return out
    return list(_CHUNKS[:limit])
