import os, secrets
from typing import Optional

from fastapi import FastAPI, UploadFile, Form, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from itsdangerous import TimestampSigner, BadSignature

from parsers import pdf_to_text, docx_to_text
from enhancers import enhance, score, cover_letter as cl_gen, linkedin_summary as li_gen
from db import get_user, bump_use, set_premium

import markdown as mdlib

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(16))
SIGNER = TimestampSigner(SECRET)
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "1"))

SESSION_COOKIE = "rid"

def get_or_set_session(request: Request, response: Response) -> str:
    rid = request.cookies.get(SESSION_COOKIE)
    if rid:
        try:
            return SIGNER.unsign(rid, max_age=60*60*24*365).decode()
        except BadSignature:
            pass
    new_id = secrets.token_hex(12)
    signed = SIGNER.sign(new_id).decode()
    response.set_cookie(SESSION_COOKIE, signed, httponly=True, samesite='Lax')
    return new_id

@app.get("/health")
def health():
    return {"ok": True, "provider": os.getenv("PROVIDER", "openai")}

@app.get("/api/usage")
async def usage(request: Request, response: Response):
    uid = get_or_set_session(request, response)
    u = get_user(uid)
    return {"free_limit": FREE_LIMIT, "uses": u["uses"], "premium": bool(u["premium"]) }

@app.post("/api/usage/increment")
async def usage_inc(request: Request, response: Response):
    uid = get_or_set_session(request, response)
    bump_use(uid)
    u = get_user(uid)
    return {"free_limit": FREE_LIMIT, "uses": u["uses"], "premium": bool(u["premium"]) }

@app.post("/api/enhance")
async def api_enhance(
    file: Optional[UploadFile] = None,
    resume_text: Optional[str] = Form(default=None),
    job_desc: Optional[str] = Form(default=None),
    tone: str = Form(default="professional"),
    request: Request = None,
    response: Response = None,
):
    try:
        uid = get_or_set_session(request, response)
        user = get_user(uid)
        if not user["premium"] and user["uses"] >= FREE_LIMIT:
            return JSONResponse({"error": "limit_reached", "message": "Free limit reached. Please upgrade to continue."}, status_code=402)

        text = resume_text or ""
        if file is not None:
            data = await file.read()
            if file.filename.lower().endswith(".pdf"):
                text = pdf_to_text(data)
            elif file.filename.lower().endswith(".docx"):
                text = docx_to_text(data)
            else:
                return JSONResponse({"error": "Unsupported file type"}, status_code=400)

        if not text.strip():
            return JSONResponse({"error": "No resume content provided"}, status_code=400)

        improved = enhance(text, job_desc, tone)
        grading = score(improved)

        bump_use(uid)
        return {"improved_markdown": improved, **grading}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/cover-letter")
async def api_cover_letter(
    resume_text: str = Form(...),
    job_desc: str = Form(...),
    tone: str = Form(default="professional"),
):
    try:
        text = resume_text.strip()
        jd = job_desc.strip()
        if not text or not jd:
            return JSONResponse({"error": "Provide resume_text and job_desc"}, status_code=400)
        letter = cl_gen(text, jd, tone)
        return {"cover_letter": letter}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/linkedin")
async def api_linkedin(
    resume_text: str = Form(...),
    tone: str = Form(default="professional"),
):
    try:
        text = resume_text.strip()
        if not text:
            return JSONResponse({"error": "Provide resume_text"}, status_code=400)
        about = li_gen(text, tone)
        return {"about": about}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/export/html")
async def export_html(markdown_text: str = Form(...)):
    html_body = mdlib.markdown(markdown_text)
    html_prefix = "<!doctype html><html><head><meta charset='utf-8'><style>"
    css = "body{font-family:Arial,Helvetica,sans-serif;max-width:780px;margin:40px auto;line-height:1.5;color:#111}"           "h1,h2,h3{margin-top:1.2em}"           "ul{margin-left:1.2em}"
    html_suffix = "</style></head><body>" + html_body + "</body></html>"
    return HTMLResponse(content=html_prefix + css + html_suffix)

# ---- Payment stubs ----
@app.post("/api/pay/init")
async def pay_init(request: Request, response: Response, email: str = Form(...), provider: str = Form("paystack")):
    uid = get_or_set_session(request, response)
    amount_kobo = int(os.getenv("PRICE_KOBO", "250000"))
    if provider == "paystack":
        return {"provider": "paystack", "authorization_url": "https://paystack.com/pay/TEST-CHECKOUT?ref=TEST-REF"}
    else:
        return {"provider": "stripe", "checkout_url": "https://checkout.stripe.com/pay/test_session"}

@app.post("/api/pay/verify")
async def pay_verify(request: Request, response: Response, reference: str = Form(...)):
    uid = get_or_set_session(request, response)
    if "PAID" in reference.upper():
        set_premium(uid, 1)
        return {"ok": True, "premium": True}
    return {"ok": False, "premium": False}
