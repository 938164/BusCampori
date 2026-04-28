import os
import time
import shutil
import sqlite3
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# CONFIGURAÇÃO DE DIRETÓRIOS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Usar /tmp é essencial no Render para evitar o erro de permissão
DB_PATH = "/tmp/bus_campori.db"
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Inicialização do Banco de Dados usando SQLite padrão para garantir a criação
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS assentos (
            numero INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'livre',
            timestamp INTEGER DEFAULT 0,
            nome TEXT DEFAULT '',
            nascimento TEXT DEFAULT '',
            pai TEXT DEFAULT '',
            mae TEXT DEFAULT '',
            pagamento TEXT DEFAULT ''
        )
    """)
    c.execute("SELECT COUNT(*) FROM assentos")
    if c.fetchone()[0] == 0:
        for i in range(1, 61):
            c.execute("INSERT INTO assentos (numero, status, timestamp) VALUES (?, 'livre', 0)", (i,))
        conn.commit()
    conn.close()

# Tenta iniciar o banco
init_db()

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Limpeza de expirados (5 minutos)
    agora = int(time.time())
    limite = agora - 300
    
    conn = get_db_conn()
    cursor = conn.cursor()
    # Libera reservas antigas
    cursor.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
    conn.commit()
    
    # Busca assentos
    cursor.execute("SELECT numero, status FROM assentos")
    assentos = cursor.fetchall()
    conn.close()
    
    return templates.TemplateResponse("index.html", {"request": request, "assentos": assentos})

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    agora = int(time.time())
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # Tenta reservar se estiver livre
    cursor.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    
    cursor.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    res = cursor.fetchone()
    conn.close()
    
    if res and res['status'] == 'reservado':
        return templates.TemplateResponse("form.html", {"request": request, "num": num})
    
    return HTMLResponse("<script>alert('Assento já ocupado!'); window.location.href='/';</script>")

@app.post("/confirmar")
async def confirmar(
    assento: int = Form(...), nome: str = Form(...), nascimento: str = Form(...),
    pai: str = Form(...), mae: str = Form(...), pagamento: str = Form(...),
    comprovante: UploadFile = File(...)
):
    # Salva comprovante em /tmp
    file_path = f"/tmp/comprovante_{assento}_{int(time.time())}.jpg"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)
        
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE assentos SET status='pago', nome=?, nascimento=?, pai=?, mae=?, pagamento=?, timestamp=0 
        WHERE numero=?
    """, (nome, nascimento, pai, mae, pagamento, assento))
    conn.commit()
    conn.close()
    
    return HTMLResponse("<h1>Reserva Confirmada!</h1><script>setTimeout(()=>window.location.href='/', 3000)</script>")