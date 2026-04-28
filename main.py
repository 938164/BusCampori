import os
import time
import sqlite3
import shutil
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Garante que o Render encontre as pastas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
# Usar /tmp é a única forma garantida de escrita no Render gratuito
DB_PATH = "/tmp/campori.db"

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS assentos (
            numero INTEGER PRIMARY KEY, status TEXT, timestamp INTEGER)""")
        c.execute("SELECT COUNT(*) FROM assentos")
        if c.fetchone()[0] == 0:
            for i in range(1, 61):
                c.execute("INSERT INTO assentos (numero, status, timestamp) VALUES (?, 'livre', 0)", (i,))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao iniciar banco: {e}")

init_db()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        conn = sqlite3.connect(DB_PATH)
        # Limpa expirados (5 minutos)
        limite = int(time.time()) - 300
        conn.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
        conn.commit()
        
        c = conn.cursor()
        c.execute("SELECT numero, status FROM assentos")
        assentos = c.fetchall()
        conn.close()
        return templates.TemplateResponse("index.html", {"request": request, "assentos": assentos})
    except Exception as e:
        return HTMLResponse(f"Erro no banco: {e}")

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        agora = int(time.time())
        conn.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
        conn.commit()
        
        c = conn.cursor()
        c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
        status = c.fetchone()[0]
        conn.close()
        
        if status == 'reservado':
            return templates.TemplateResponse("form.html", {"request": request, "num": num})
        return HTMLResponse("<script>alert('Ocupado!'); window.location.href='/';</script>")
    except:
        return HTMLResponse("<script>window.location.href='/';</script>")

@app.post("/confirmar")
async def confirmar(assento: int = Form(...), comprovante: UploadFile = File(...)):
    try:
        # Salva o comprovante em /tmp (único lugar permitido)
        path = f"/tmp/foto_{assento}.jpg"
        with open(path, "wb") as buffer:
            shutil.copyfileobj(comprovante.file, buffer)
            
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE assentos SET status='pago', timestamp=0 WHERE numero=?", (assento,))
        conn.commit()
        conn.close()
        return HTMLResponse("<h1>Sucesso!</h1><script>setTimeout(()=>window.location.href='/', 2000)</script>")
    except:
        return HTMLResponse("Erro ao confirmar.")