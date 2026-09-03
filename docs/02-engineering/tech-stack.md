# Technology Stack

## 1. Purpose

This document defines the technologies used to implement the Receivables Resolution Agent.

The technology choices prioritize:

1. correctness for financial workflows,
2. deterministic business logic,
3. AI/LLM integration,
4. rapid buildathon development,
5. testability,
6. explainability,
7. maintainability, and
8. straightforward local development.

The project will use a **modular monolith** rather than a distributed microservice architecture.

---

# 2. Architecture Style

## Decision

**Modular Monolith**

The application will initially run as a small number of deployable applications with clearly separated internal modules.

Primary components:

```text
Frontend
    +
Backend
    +
PostgreSQL

The backend contains logical modules for:

recovery cases,
AI reasoning,
evidence,
policy,
state management,
Razorpay integration,
audit,
evaluation.

These modules communicate through explicit interfaces.

Why

A modular monolith provides:

simpler local development,
lower operational complexity,
easier debugging,
easier buildathon deployment,
strong separation of responsibilities,
less infrastructure overhead than microservices.

The project does not require independently scalable services for the MVP.

Microservices may be considered only if a demonstrated requirement emerges.

3. Backend
Technology

Python 3.12+

Python is selected because the project requires:

AI/LLM integration,
structured data processing,
benchmark execution,
evaluation tooling,
test automation,
document/evidence processing,
financial workflow orchestration.

Python also allows the AI and evaluation code to share the same language and domain models.

4. API Framework
Technology

FastAPI

FastAPI is responsible for:

REST APIs,
request validation,
response validation,
webhook endpoints,
dependency injection,
API documentation.

FastAPI works well with Pydantic and asynchronous I/O where required.

The API layer should remain thin.

Business logic must live in domain/services modules rather than inside route handlers.

5. Data Validation
Technology

Pydantic

Pydantic will be used for:

API request models,
API response models,
AI output schemas,
domain input validation,
configuration validation,
structured data validation.

LLM responses must pass Pydantic validation before being accepted by the application.

Invalid model output must never reach financial execution code.

6. Database
Technology

PostgreSQL

PostgreSQL is the primary persistent datastore.

It will store:

merchants,
customers,
invoices,
invoice lines,
recovery cases,
disputes,
evidence metadata,
agent runs,
resolution proposals,
policy decisions,
recovery actions,
payments,
outreach records,
human approvals,
audit events.
Why PostgreSQL

The domain contains strong relationships and financial consistency requirements.

A relational database provides:

foreign-key constraints,
transactions,
strong consistency,
structured querying,
constraints,
JSONB support,
reliable aggregation,
mature tooling.
7. ORM
Technology

SQLAlchemy 2.x

SQLAlchemy will provide:

database models,
transactions,
queries,
relationship management,
repository implementation.

Database access should be isolated from business logic.

8. Database Migrations
Technology

Alembic

Alembic will manage database schema migrations.

Schema changes must be represented as versioned migrations rather than manual database modifications.

9. Frontend
Technology

Next.js + TypeScript

The frontend will provide the finance-operations dashboard.

Primary responsibilities:

recovery dashboard,
case list,
case detail,
evidence viewer,
resolution proposal display,
policy result display,
payment status,
audit timeline,
benchmark results.
10. Frontend UI
Technology

React

Next.js will provide the application framework while React will be used to construct UI components.

The frontend should prioritize:

clarity,
financial visibility,
decision traceability,
responsive interaction,
minimal unnecessary animation.

The interface should make the financial workflow understandable without requiring users to understand the underlying AI architecture.

11. Styling
Initial choice

Use a lightweight component/styling approach that supports fast development and consistent UI.

The exact styling library may be finalized during implementation, but the MVP should avoid introducing unnecessary frontend complexity.

The frontend must remain subordinate to the core financial workflow.

12. AI / LLM Layer
Technology

LLM API with structured output support

The project will use an LLM for semantic tasks such as:

customer-objection understanding,
issue classification,
evidence interpretation,
structured fact extraction,
resolution recommendation.

The LLM is not the financial authority.

AI boundary

The LLM must never directly:

mark an invoice paid,
calculate authoritative payment success,
bypass policy,
bypass the state machine,
execute Razorpay actions,
override a legal lock,
alter financial state without deterministic validation.
13. AI Output Format

All AI outputs must be structured.

Example:

{
  "issue_type": "QUANTITY_DISPUTE",
  "confidence": 0.96,
  "evidence_ids": ["E-001", "E-002"]
}

The application validates AI responses against predefined Pydantic schemas.

Free-form model output must not be passed directly to financial services.

14. AI Orchestration

The MVP will use a simple application-controlled orchestration layer.

Logical reasoning components:

Triage Agent
Evidence Agent
Resolution Agent

The orchestration flow is deterministic:

Case
 ↓
Triage
 ↓
Evidence
 ↓
Resolution
 ↓
Policy
 ↓
State Machine
 ↓
Execution

The project will not use unrestricted autonomous multi-agent conversations.

15. Retrieval / RAG
Initial approach

No mandatory vector database in the first MVP.

Synthetic benchmark data will initially be represented using structured records and small evidence documents.

The application should introduce retrieval augmentation only when it provides a demonstrated benefit for the evidence workflow.

Optional technology

pgvector

If long-form evidence retrieval becomes necessary, pgvector may be enabled within PostgreSQL rather than introducing a separate vector database.

This keeps the infrastructure simple.

16. Razorpay Integration
Technology

Razorpay APIs

Razorpay will provide the payment execution layer for approved recovery actions.

The application will isolate Razorpay-specific code behind a dedicated integration module.

Responsibilities include:

payment request creation,
external reference handling,
payment status lookup where required,
webhook verification,
event processing.

The LLM must never call Razorpay directly.

17. Webhook Processing

Razorpay webhook events will be processed by the backend.

The webhook pipeline is:

Incoming event
      ↓
Signature verification
      ↓
Schema validation
      ↓
Idempotency check
      ↓
Locate associated payment/action
      ↓
Update payment state
      ↓
State-machine transition
      ↓
Audit event

Webhook processing must be safe to retry.

18. Financial Representation
Rule

All monetary values inside the financial domain should use an exact representation.

For INR, the preferred internal representation is integer paise.

Example:

₹9,00,000

is represented internally as:

90000000

Floating-point arithmetic must not be used for authoritative monetary calculations.

19. Testing
Backend

pytest

pytest will be used for:

unit tests,
policy tests,
state-machine tests,
service tests,
integration tests.
Frontend

The frontend may use the testing tools supported by the selected Next.js/React setup.

The exact frontend testing framework can be finalized during implementation.

Core testing principle

Deterministic financial controls must have automated tests independent of the LLM.

20. Static Analysis and Code Quality

The backend should use:

Ruff

for linting and formatting.

Type checking may use:

Pyright or another appropriate Python type checker.

The final choice should remain lightweight and compatible with the development workflow.

21. API Documentation

FastAPI's generated OpenAPI documentation will be used as the primary interactive API reference during development.

The human-readable API contract remains documented separately in:

docs/02-engineering/api-contracts.md
22. Configuration and Secrets

Secrets must never be committed to the repository.

Configuration will use environment variables.

Required secret examples will be represented in:

.env.example

Potential values include:

DATABASE_URL
LLM_API_KEY
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET

Actual secrets must remain local or in the deployment secret manager.

23. Containerization
Technology

Docker + Docker Compose

Docker will be used to simplify local execution of:

PostgreSQL,
backend,
optionally frontend.

The initial development workflow should remain easy to run without requiring Kubernetes or a cloud infrastructure stack.

24. Deployment

Deployment technology will be chosen after the MVP is functional.

The deployment must support:

backend API,
frontend,
PostgreSQL,
HTTPS webhook endpoint for Razorpay.

The specific hosting provider is an implementation/deployment decision, not a product requirement.

25. What We Are Intentionally NOT Using Initially

The MVP will not introduce:

Kubernetes,
Kafka,
complex message brokers,
microservices,
Airflow,
large agent frameworks,
separate vector databases,
complex distributed tracing platforms,
multiple databases,
autonomous agent swarms.

These technologies may be reconsidered only if a concrete requirement appears.

The objective is to maximize engineering quality rather than infrastructure complexity.

26. Technology Decision Summary
Layer	Technology
Backend language	Python 3.12+
Backend framework	FastAPI
Validation	Pydantic
ORM	SQLAlchemy 2.x
Database	PostgreSQL
Migrations	Alembic
Frontend	Next.js
Frontend language	TypeScript
UI	React
AI	LLM API with structured outputs
Payment	Razorpay APIs
Testing	pytest
Linting/formatting	Ruff
Type checking	Pyright or equivalent
Containers	Docker / Docker Compose
Retrieval (optional)	pgvector
27. Core Technology Principle

Technology choices must serve the financial workflow.

The project prioritizes:

Correctness
    >
Safety
    >
Testability
    >
Observability
    >
Developer velocity
    >
Feature count

The system should remain understandable to an engineer reviewing the repository.
