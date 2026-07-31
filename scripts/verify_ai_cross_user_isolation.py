#!/usr/bin/env python3
"""Verify AI conversations, runs, and messages cannot cross user boundaries."""
from __future__ import annotations
import os, sys
from pathlib import Path
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1]

def main() -> None:
    sys.path.insert(0,str(ROOT/"app")); os.environ.setdefault("FLASK_ENV","testing"); os.environ.setdefault("WMS_SKIP_DB_UPGRADE","1")
    import app as wms
    from ai.models import AIConversation, AIMessage
    wms.app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.create_all(); users=[]
        for name in ("ai_owner","ai_other"):
            user=wms.User.query.filter_by(username=name).first()
            if not user: user=wms.User(username=name,role="warehouse",status="normal",password_hash=generate_password_hash("Password123!")); wms.db.session.add(user)
            users.append(user)
        wms.db.session.commit(); owner, other=users
        run=wms.AIRun(user_id=owner.id,request_id="cross-user-run",request_hash="a"*64,endpoint="/test")
        conv=AIConversation(user_id=owner.id,title="owner"); wms.db.session.add_all([run,conv]); wms.db.session.flush()
        message=AIMessage(conversation_id=conv.id,ai_run_id=run.id,role="assistant",content="private"); wms.db.session.add(message); wms.db.session.commit(); ids=(conv.id,run.id,message.id)
    client=wms.app.test_client(); assert client.post("/login",data={"username":"ai_other","password":"Password123!"}).status_code in (302,303)
    conv_id,run_id,msg_id=ids
    assert client.get(f"/api/ai/conversations/{conv_id}").status_code==404
    assert client.post(f"/api/ai/conversations/{conv_id}/messages",json={"role":"user","content":"x"}).status_code==404
    assert client.post("/api/ai/feedback",json={"rating":"up","ai_run_id":run_id}).status_code==403
    assert client.post("/api/ai/feedback",json={"rating":"up","ai_message_id":msg_id}).status_code==403
    print("PASS: AI cross-user conversation, run, and message access is denied")
if __name__=="__main__": main()
