# Business Overview — Dual-System Procurement AI POC

**Audience**: procurement leaders, sourcing managers, finance partners, IT/security stakeholders  
**Purpose**: translate the repository into business value, define use cases, caveats, and an Azure-aligned path to production.

---

## 1) Executive summary

This repository contains **two complementary procurement capabilities**:

1. **Opportunity Heatmap** (early-warning + prioritization): continuously scores and ranks **renewals** and **new requests** into **T1–T4** so teams focus on the highest-value / highest-urgency work first.
2. **Legacy DTP ProcuraBot** (execution + governance): a structured, human-in-the-loop copilot that helps execute sourcing work through **DTP-01 → DTP-06**, producing artifacts (strategy, RFx, scoring, negotiation, contract, implementation) and capturing decisions for traceability.

**How they work together**: Heatmap identifies and prioritizes opportunities; when a human approves an opportunity, it can create a new DTP case to execute the work in a governed workflow.

---

## 2) What business problem this solves

### Problem A — prioritization is inconsistent and reactive
Procurement teams often rely on scattered spreadsheets, tribal knowledge, and ad-hoc escalation. This leads to:
- late renewals (avoidable price uplifts)
- missed savings opportunities
- “loudest stakeholder wins” prioritization
- inconsistent treatment of supplier risk / concentration

### Problem B — execution is slow and knowledge is trapped
Even when priorities are clear, execution can be slow due to:
- repeated effort (rebuilding RFx templates, evaluation criteria, negotiation plans)
- hard-to-find history and evidence
- inconsistent governance artifacts and decision logs

**Business goal**: improve **consistency, speed, and auditability** while keeping humans in control.

---

## 3) Business users and where value accrues

- **Sourcing / Category Managers**
  - quicker triage of what to do next
  - consistent scoring and rationale
  - reusable artifact generation (RFx, negotiation, etc.)

- **Procurement Operations / PMO**
  - predictable stage gating, readiness checks, decision tracking
  - reduced cycle time through standardized workflows

- **Finance**
  - better prioritization toward high-value categories
  - clearer business cases and savings narratives

- **Risk / Compliance / Legal**
  - more transparent rationale and governance traceability
  - early risk flags and concentration indicators

- **Stakeholders / Requesters**
  - clearer “what happens next” and expected timelines

---

## 4) Defined use cases (with examples)

### Use case 1 — “Which renewals require immediate sourcing action?”
**User**: category manager / sourcing lead  
**Flow**:
1. Heatmap runs scoring and ranks renewals.
2. User filters to **T1** and reviews the top set.
3. User approves a few T1 opportunities to create DTP cases.
**Value**: fewer last-minute renewals, better negotiation leverage.

### Use case 2 — “We got a new business intake request — how urgent is it?”
**User**: procurement intake coordinator  
**Flow**:
1. Request is entered via Heatmap intake.
2. System produces a **PS_new score** and tier (T1–T4).
3. Request is prioritized versus existing pipeline.
**Value**: consistent prioritization at the front door.

### Use case 3 — “Explain why Opportunity A is ranked above B”
**User**: stakeholder, manager, reviewer  
**Flow**:
1. Heatmap copilot explains ranking using current opportunity rows and recent feedback history.
2. Scores are not overwritten; explanation is for decision support.
**Value**: faster alignment, fewer manual spreadsheet debates.

### Use case 4 — “Governed end-to-end sourcing with artifact continuity”
**User**: sourcing manager, legal, finance  
**Flow**:
1. A DTP case runs through stages with explicit decisions (approve/reject).
2. Artifacts are generated/updated with traceable grounding.
3. The system records decisions and outputs for auditability.
**Value**: repeatable execution, less rework, stronger governance.

---

## 5) How to interpret tiers (T1–T4) in business terms

Tiers are a **priority signal**, not an autonomous decision.

- **T1 (Critical)**: act now; likely high urgency and/or high value and/or strong risk signal.
- **T2 (High)**: plan within the quarter; meaningful opportunity.
- **T3 (Medium)**: monitor; queue for later sourcing planning.
- **T4 (Low)**: deprioritize; keep in view but don’t spend cycles.

The scoring logic is intentionally explainable and can be tuned (weights, category strategy cards, thresholds).

---

## 6) Caveats and what this POC is (and is not)

### Key caveats
- **Synthetic data**: current demo data is illustrative; real-world results depend on your spend/contract quality.
- **No authentication/authorization** (POC): production requires identity, roles, and tenant isolation.
- **Not a “self-driving procurement” tool**: the systems provide decision support; humans approve key steps.
- **LLM limitations**:
  - LLM outputs must be treated as **assistive** and **bounded**
  - explanations can drift; rely on stored scores and evidence
- **Data quality dependency**: missing contract dates, inconsistent supplier names, or incorrect category mapping will reduce scoring fidelity.

### What the POC is designed to prove
- A practical prioritization layer (Heatmap) that teams can adopt quickly
- A governed execution workflow (DTP) that standardizes artifacts and decisions
- A safe way to add LLMs without losing control (bounded learning + interpreter fallbacks)

---

## 7) What “AI” means here (business translation)

This repo uses “AI” in three practical ways:

1. **Deterministic scoring** (reliability-first): consistent calculations for urgency/value/risk/concentration/strategy alignment.
2. **LLM-assisted interpretation** (robustness): when data is messy (dates/status labels), an LLM can extract/normalize structured fields—only as a fallback.
3. **Human feedback memory** (continuous improvement): reviewer corrections are stored and can nudge future scoring in a bounded, explainable way.

This combination aims to deliver an “AI feel” (context, explanation, learning) while keeping governance and predictability.

---

## 8) KPIs to measure business impact

Suggested metrics for pilots and rollout:

- **Cycle time**: days from intake → award decision (median / P90)
- **Renewal timeliness**: % renewals started ≥ X days before expiry
- **Savings / avoidance**: sourced value prioritized by tier; realized savings rate
- **Override rate**: how often humans override tier/score (and why)
- **Adoption**: active users per week; # opportunities reviewed; # cases created from heatmap
- **Compliance**: completeness of required artifacts per stage; audit log coverage

---

## 9) Azure-aligned future implementation (production path)

### 9.1 Reference architecture (Azure)

**App hosting**
- **FastAPI backend** → Azure App Service or Azure Container Apps
- **Next.js frontend** → Azure Static Web Apps or App Service

**Data**
- **Operational data** (cases, opportunities) → Azure SQL Database (or PostgreSQL Flexible Server)
- **Files** (RFPs, contracts, proposals) → Azure Blob Storage
- **Events / pipelines** → Azure Functions + Event Grid (optional)

**AI**
- **LLMs** → Azure OpenAI (chat models)
- **Embeddings & vector search** → Azure AI Search (vector + hybrid) or Postgres pgvector
- **Prompt governance** → Azure AI Studio / prompt flows (optional)

**Security & identity**
- Microsoft Entra ID authentication (users + service principals)
- Managed Identity for service-to-service access
- Private networking (Private Endpoints) for data/AI where required

**Observability**
- Application Insights + Log Analytics
- Structured audit events for approvals, overrides, and model usage

### 9.2 Key production requirements (non-negotiables)
- **RBAC**: roles like requester, reviewer, category manager, admin, auditor
- **Data lineage**: link every decision and artifact to inputs and timestamped context
- **Environment separation**: dev/test/prod with separate data and model deployments
- **PII/secret handling**: redaction, safe logging, key vault usage
- **Cost controls**: rate limiting, caching, tiered model usage, “LLM off” fallback mode

### 9.3 Integrations to plan for
- CLM (contract metadata + dates): e.g., Icertis/Ariba/ServiceNow/Workday/ERP exports
- Spend / PO data: ERP (SAP/Oracle) or data warehouse
- Supplier risk: 3rd-party risk ratings and internal performance systems

### 9.4 Future enhancements (business-facing)
- **Role-based dashboards** (what each persona sees first)
- **Category strategy governance** (approval workflows for category cards)
- **Explainability**:
  - show component contributions + evidence snippets in UI
  - “what changed since last run” diffs (especially when learning applies)
- **Advanced learning loop**:
  - component-level reviewer corrections drive bounded model updates
  - per-category calibration (weights/thresholds by category)
- **Enterprise controls**:
  - policy checks as “soft gates” or optional hard gates (configurable)

---

## 10) Recommended pilot plan (pragmatic)

1. **Pilot scope**: pick 1–3 categories (IT infrastructure + one indirect category)
2. **Data onboarding**: contract dates + contract values + supplier risk input
3. **Heatmap adoption**: weekly prioritization ritual (T1/T2 review)
4. **DTP execution**: run a handful of T1 opportunities through DTP for artifact standardization
5. **Measure**: cycle time, override rate, renewal timeliness, stakeholder satisfaction
6. **Decide**: expand categories and integrate with Azure-native data and identity

---

## Appendix: Glossary (business)

- **DTP**: Dynamic Transaction Pipeline — staged methodology from Strategy through Implementation.
- **Opportunity Heatmap**: scoring + ranking of renewals/new requests into tiers for prioritization.
- **Tier (T1–T4)**: priority classification derived from score thresholds.
- **RAG**: Retrieval Augmented Generation — LLM uses retrieved documents to ground outputs.
- **Chroma / Vector store**: stores embeddings for similarity search (used for document retrieval and feedback memory).

