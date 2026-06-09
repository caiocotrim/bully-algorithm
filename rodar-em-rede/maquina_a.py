import socket
import threading
import json
import time

HOST = "0.0.0.0"           # Aceita conexões de qualquer interface
IP_REMOTO = "10.12.2.161"   # ← IP da Máquina B (ajuste se necessário)
PORTA_LOCAL = 5000
PORTA_REMOTA = 5001

TEMPO = 2


class Processo:
    def __init__(self, pid):
        self.pid = pid
        self.ativo = True

    def __str__(self):
        status = "Ativo" if self.ativo else "Inativo"
        return f"Processo {self.pid} ({status})"


class Valentao:
    def __init__(self):
        self.processos = []
        self.coordenador = 8

    def adicionar_processo(self, processo):
        self.processos.append(processo)

    def buscar_processo(self, pid):
        for processo in self.processos:
            if processo.pid == pid:
                return processo
        return None

    def enviar(self, mensagem):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                s.connect((IP_REMOTO, PORTA_REMOTA))
                s.send(json.dumps(mensagem).encode())

                resposta = s.recv(4096)
                if resposta:
                    return json.loads(resposta.decode())

        except Exception as e:
            print(f"[Erro ao conectar em {IP_REMOTO}:{PORTA_REMOTA}] {e}")
            return None

    def mostrar_estado(self):
        print("\n=== MÁQUINA A ===")

        for processo in self.processos:
            status = "Ativo" if processo.ativo else "Inativo"

            if processo.pid == self.coordenador:
                print(f"{processo.pid} - {status} (Coordenador)")
            else:
                print(f"{processo.pid} - {status}")

        print()

    def iniciar_eleicao(self, pid):
        print(f"\nProcesso {pid} iniciou eleição")
        time.sleep(TEMPO)

        maiores_locais = [
            p.pid
            for p in self.processos
            if p.ativo and p.pid > pid
        ]

        resposta = self.enviar({"tipo": "maior_ativo"})

        if resposta is None:
            print("[Aviso] Máquina B não respondeu. Usando apenas processos locais.")
            maior_remoto = -1
        else:
            maior_remoto = resposta["pid"]

        candidatos = maiores_locais[:]

        if maior_remoto > pid:
            candidatos.append(maior_remoto)

        if not candidatos:
            self.definir_novo_coordenador(pid)
            return

        vencedor = max(candidatos)

        print(f"Processo {vencedor} respondeu")
        time.sleep(TEMPO)

        if vencedor in [1, 3, 5, 7]:
            self.iniciar_eleicao(vencedor)
        else:
            self.enviar({"tipo": "eleicao", "pid": vencedor})

    def definir_novo_coordenador(self, pid):
        self.coordenador = pid

        print(f"\nProcesso {pid} virou coordenador")

        self.enviar({"tipo": "coordenador", "pid": pid})

    def atualizar_coordenador(self, pid):
        self.coordenador = pid

        print(f"\nNovo coordenador recebido: {pid}")


sistema = Valentao()

for pid in [1, 3, 5, 7]:
    sistema.adicionar_processo(Processo(pid))


def servidor():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORTA_LOCAL))
    srv.listen()

    print(f"[Servidor] Escutando em {HOST}:{PORTA_LOCAL}")

    while True:
        conn, addr = srv.accept()
        print(f"[Servidor] Conexão recebida de {addr}")

        dados = conn.recv(4096)

        if not dados:
            conn.close()
            continue

        msg = json.loads(dados.decode())

        if msg["tipo"] == "maior_ativo":

            ativos = [
                p.pid
                for p in sistema.processos
                if p.ativo
            ]

            conn.send(
                json.dumps({"pid": max(ativos)}).encode()
            )

        elif msg["tipo"] == "coordenador":

            sistema.atualizar_coordenador(msg["pid"])
            conn.send(b"{}")

        elif msg["tipo"] == "eleicao":

            conn.send(b"{}")
            conn.close()
            threading.Thread(
                target=sistema.iniciar_eleicao,
                args=(msg["pid"],),
                daemon=True
            ).start()
            continue

        conn.close()


threading.Thread(target=servidor, daemon=True).start()

print("Máquina A pronta")
sistema.mostrar_estado()

while True:
    time.sleep(1)