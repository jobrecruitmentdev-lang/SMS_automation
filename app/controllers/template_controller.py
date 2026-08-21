import os
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Query
from app.models.template import ValidateSmsRequest, SmsEncodingMetrics, CloudTemplateModel
from app.services.ai_service import evaluate_spintax, calculate_sms_encoding
from app.core.config import TEMPLATES_FILE, settings
from app.core.state import write_log

router = APIRouter(tags=["SMS Templates & Spintax Validator"])

@router.post("/api/validate_sms", response_model=SmsEncodingMetrics)
def validate_sms(req: ValidateSmsRequest):
    spun_text = evaluate_spintax(req.text, req.seed or 0)
    metrics = calculate_sms_encoding(spun_text)
    metrics["spun_preview"] = spun_text
    return SmsEncodingMetrics(**metrics)

@router.get("/api/cloud_templates")
def get_cloud_templates(user_id: str = Query(None)):
    if settings.SUPABASE_DB_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(settings.SUPABASE_DB_URL, connect_timeout=4)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS studio_templates (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title VARCHAR(150) NOT NULL,
                    template_body TEXT NOT NULL,
                    category VARCHAR(50) DEFAULT 'recruitment',
                    visibility VARCHAR(20) DEFAULT 'public',
                    user_id VARCHAR(100),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("SELECT id, title, template_body, category, visibility, user_id FROM studio_templates ORDER BY created_at DESC LIMIT 50")
            rows = cur.fetchall()
            conn.close()
            if rows:
                return {"ok": True, "templates": [{"id": str(r[0]), "title": r[1], "template_body": r[2], "category": r[3], "visibility": r[4], "user_id": r[5]} for r in rows]}
        except Exception as e:
            write_log(f"Supabase templates fetch error: {e}")

    # Fallback to local templates
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                return {"ok": True, "templates": json.load(f)}
        except Exception:
            pass
    return {"ok": True, "templates": []}

@router.post("/api/cloud_templates")
def save_cloud_template(req: CloudTemplateModel):
    if settings.SUPABASE_DB_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(settings.SUPABASE_DB_URL, connect_timeout=4)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO studio_templates (title, template_body, category, visibility, user_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (req.title, req.template_body, req.category or "recruitment", req.visibility or "public", req.user_id))
            new_id = cur.fetchone()[0]
            conn.close()
            return {"ok": True, "id": str(new_id), "message": "Template saved to Cloud DB."}
        except Exception as e:
            write_log(f"Supabase template save error: {e}")

    # Fallback to local file
    templates = []
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                templates = json.load(f)
        except Exception:
            pass
    t_obj = req.dict()
    t_obj["id"] = str(uuid.uuid4())
    t_obj["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    templates.insert(0, t_obj)
    try:
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, indent=2)
    except Exception:
        pass
    return {"ok": True, "id": t_obj["id"], "message": "Template saved locally."}
