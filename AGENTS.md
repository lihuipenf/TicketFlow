# TicketFlow development

- Project: D:\agent ai\TicketFlow. Preserve existing files and migration backups.
- All temp and dependency caches must remain under D:\CodexData as instructed by the workspace.
- Python backend: FastAPI, SQLAlchemy/MySQL, durable single Worker, Milvus Lite, local Qwen3 Embedding. Frontend: Vue 3/TypeScript/Element Plus.
- Never commit .env, passwords, customer data, uploads, generated indexes, model weights or logs. Keep .env.example current.
- Run backend tests after each backend module, frontend tests/build after UI changes, and end-to-end verification before claiming completion.
- Test doubles belong only in tests. Missing model credentials must be explicit; never present canned output as a real LLM response.
- Model output and imported documents are untrusted. Validate citations, sanitize sensitive fields, enforce role checks and human approval before sending.
- Worker owns Milvus access. Publish a knowledge version only after both vector and lexical indexes are ready. Retain citation snapshots.
- Keep processing resumable and idempotent. Record failures without credentials or raw provider response bodies.
- Runtime data belongs in ./data (ignored); model cache in D:\CodexData\caches\huggingface.
- Commands and verified limitations are documented in README.md and docs/verification.md.
