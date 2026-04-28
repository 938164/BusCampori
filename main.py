import os
import time
import sqlite3
import shutil
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Definição de caminhos absoluta para evitar erros no Render.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = "/tmp/campori_vFinal.db"
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

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
                c.execute("INSERT INTO assentos VALUES (?, 'livre', 0)", (i,))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro banco: {e}")

init_db()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = sqlite3.connect(DB_PATH)
    agora = int(time.time())
    # Limpa automaticamente reservas com mais de 5 minutos
    conn.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (agora - 300,))
    conn.commit()
    c = conn.cursor()
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    conn.close()
    # O uso de name= e context= é obrigatório nas versões novas
    return templates.TemplateResponse(request=request, name="index.html", context={"assentos": dados})

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    conn = sqlite3.connect(DB_PATH)
    agora = int(time.time())
    conn.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    c = conn.cursor()
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    res = c.fetchone()
    conn.close()
    if res and res[0] == 'reservado':
       return templates.TemplateResponse(request=request, name="form.html", context={"num": num})
    return HTMLResponse("<script>alert('Indisponível'); window.location.href='/';</script>")

@app.post("/confirmar")
async def confirmar(assento: int = Form(...), comprovante: UploadFile = File(...)):
    foto_path = f"/tmp/comprovante_{assento}.jpg"
    with open(foto_path, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE assentos SET status='pago', timestamp=0 WHERE numero=?", (assento,))
    conn.commit()
    conn.close()
    return HTMLResponse("<h1>Reserva Confirmada!</h1><script>setTimeout(()=>window.location.href='/', 2000)</script>")
