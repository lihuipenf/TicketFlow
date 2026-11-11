# TicketFlow product context

TicketFlow is a locally deployed ecommerce support workbench. Staff receive customer inquiries, inspect associated simulated orders, retrieve published policy evidence, generate a model-assisted draft, and explicitly review it before sending to the simulated channel.

Primary users are agents, supervisors, knowledge administrators and administrators. Role and resource permissions remain enforced by the backend. The frontend supports five areas: tickets, knowledge, workflow configuration, execution logs and simulated orders.

The first implementation uses Vue 3, Vite, Element Plus and a FastAPI/MySQL backend. Local Qwen embeddings, Milvus Lite and BM25/RRF retrieval are real; order data and delivery channel are synthetic. DeepSeek generation is configured locally. Keys stay server-side.

## Requested UI upgrade, 2026-11-11

The user explicitly chose a brighter, simpler interface with a light workbench as the primary visual direction. Improve the complete existing UI and interaction with motion-v, UI UX Pro Max guidance and Impeccable review. Preserve the business workflow and human confirmation boundary.

Assumptions inferred from the supplied business brief: this is a frequently used desktop productivity tool; clarity and fast repeated operations take priority over decorative effects. Mobile layouts must remain usable. No new backend services, real ecommerce connections or payment execution are implied by the UI upgrade.
