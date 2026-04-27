from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Tempo de bloqueio (em segundos). 600 segundos = 10 minutos
TEMPO_LIMITE_RESERVA = 600 

def limpar_reservas_expiradas():
    conn = sqlite3.connect("db.sqlite")
    c = conn.cursor()
    agora = int(time.time())
    # Se o status for 'reservado' e o tempo passou do limite, volta para 'livre'
    limite = agora - TEMPO_LIMITE_RESERVA
    c.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
    conn.commit()
    conn.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Limpa os "desistentes" antes de mostrar os assentos para alguém novo
    limpar_reservas_expiradas()
    
    conn = sqlite3.connect("db.sqlite")
    c = conn.cursor()
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="index.html", context={"assentos": dados})

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    conn = sqlite3.connect("db.sqlite")
    c = conn.cursor()
    
    # Tenta reservar apenas se estiver livre
    agora = int(time.time())
    c.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    
    # Verifica se a reserva deu certo (se o assento era realmente livre)
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    resultado = c.fetchone()
    conn.close()

    if resultado and resultado[0] == 'reservado':
        return templates.TemplateResponse(request=request, name="form.html", context={"num": num})
    else:
        return HTMLResponse("<script>alert('Este assento acabou de ser pego por outra pessoa!'); window.location.href='/';</script>")

@app.post("/confirmar")
async def confirmar(
    assento: int = Form(...), 
    nome: str = Form(...), 
    nascimento: str = Form(...), 
    pai: str = Form(...), 
    mae: str = Form(...), 
    pagamento: str = Form(...),
    comprovante: UploadFile = File(...)
):
    # Salva a foto
    extensao = comprovante.filename.split(".")[-1]
    nome_foto = f"comprovante_assento_{assento}.{extensao}"
    with open(nome_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    # Finaliza a compra (Muda para 'pago' e zera o timestamp para não ser deletado)
    conn = sqlite3.connect("db.sqlite")
    c = conn.cursor()
    c.execute("""
        UPDATE assentos 
        SET status='pago', nome=?, nascimento=?, pai=?, mae=?, pagamento=?, timestamp=0 
        WHERE numero=?
    """, (nome, nascimento, pai, mae, pagamento, assento))
    conn.commit()
    conn.close()

    return HTMLResponse("<h1>✅ Sucesso! Assento confirmado.</h1><script>setTimeout(()=>window.location.href='/', 3000)</script>")