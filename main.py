from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, Form, File, UploadFile # Adicione File e UploadFile aqui
import shutil # Para salvar o arquivo no seu PC
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Conexão com Banco
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
c = conn.cursor()

# Criar tabela com todas as colunas necessárias
c.execute("""
CREATE TABLE IF NOT EXISTS assentos (
    numero INTEGER PRIMARY KEY,
    status TEXT,
    timestamp INTEGER,
    nome TEXT,
    nascimento TEXT,
    pai TEXT,
    mae TEXT,
    pagamento TEXT
)
""")

# Iniciar assentos se o banco estiver vazio
c.execute("SELECT COUNT(*) FROM assentos")
if c.fetchone()[0] == 0:
    for i in range(1, 61):
        c.execute("INSERT INTO assentos VALUES (?, 'livre', 0, '', '', '', '', '')", (i,))
    conn.commit()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    # CORREÇÃO: Passando o request corretamente para evitar o erro de 'tuple'
    return templates.TemplateResponse(
        request=request, name="index.html", context={"assentos": dados}
    )

@app.get("/reservar/{num}", response_class=HTMLResponse)
def reservar(request: Request, num: int):
    return templates.TemplateResponse(
        request=request, name="form.html", context={"num": num}
    )

@app.post("/confirmar")
async def confirmar(
    assento: int = Form(...), 
    nome: str = Form(...), 
    nascimento: str = Form(...), 
    pai: str = Form(...), 
    mae: str = Form(...), 
    pagamento: str = Form(...),
    comprovante: UploadFile = File(...) # Campo do arquivo
):
    # 1. Salva a foto do comprovante na sua pasta
    extensao = comprovante.filename.split(".")[-1]
    nome_foto = f"comprovante_assento_{assento}.{extensao}"
    with open(nome_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    # 2. Atualiza o Banco de Dados
    c.execute("UPDATE assentos SET status='pago', nome=? WHERE numero=?", (nome, assento))
    conn.commit()

    # 3. Gera o TXT (Agora avisando que tem foto)
    with open(f"reserva_{assento}.txt", "w") as f:
        f.write(f"Assento: {assento}\nNome: {nome}\nFoto salva como: {nome_foto}")

    # 4. Tela de Sucesso
    return HTMLResponse("<html><body style='background:#1a1a2e;color:white;text-align:center;padding-top:100px;'><h1>✅ Comprovante Recebido!</h1><p>Sua reserva foi finalizada com sucesso.</p><script>setTimeout(()=>window.close(), 3000)</script></body></html>")