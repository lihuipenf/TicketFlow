from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.api import router
from app.ingress import UploadIngress
from uuid import uuid4

app = FastAPI(title='TicketFlow')
app.include_router(router)
app.add_middleware(UploadIngress)
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins.split(','), allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'])


@app.get('/api/v1/health')
def health():
    return {'status': 'alive', 'service': 'TicketFlow'}


@app.middleware('http')
async def trace(request: Request, call_next):
    trace_id = uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        return JSONResponse(status_code=500, content={'detail': '服务处理失败，请检查依赖或联系管理员', 'trace_id': trace_id})
    response.headers['X-Trace-ID'] = trace_id
    return response
