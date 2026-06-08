import argparse
import json
import random
import socket
import socketserver
import threading


class Processo:
    def __init__(self, pid):
        self.pid = pid
        self.ativo = True

    def __str__(self):
        status = "Ativo" if self.ativo else "Inativo"
        return f"Processo {self.pid} ({status})"


class Valentao:
    def __init__(self, local_ids=None, peers=None):
        self.processos = []
        self.coordenador = None
        self.local_ids = set(local_ids or [])
        self.peers = peers or {}
        self.lock = threading.RLock()

    def adicionar_processo(self, processo):
        self.processos.append(processo)

    def buscar_processo(self, pid):
        for processo in self.processos:
            if processo.pid == pid:
                return processo
        return None

    def definir_coordenador_inicial(self):
        with self.lock:
            ativos = [p for p in self.processos if p.ativo]

            if ativos:
                self.coordenador = max(ativos, key=lambda p: p.pid)

    def mostrar_estado(self):
        with self.lock:
            print("\nProcessos:")

            for processo in sorted(self.processos, key=lambda p: p.pid):
                status = "Ativo" if processo.ativo else "Inativo"
                dono = "local" if self.eh_local(processo.pid) else "remoto"

                if (
                    self.coordenador
                    and processo.pid == self.coordenador.pid
                    and processo.ativo
                ):
                    print(f"{processo.pid} - {status} ({dono}, Coordenador)")
                else:
                    print(f"{processo.pid} - {status} ({dono})")

            print()

    def derrubar_processo(self, pid):
        if not self.eh_local(pid):
            self.enviar_para_dono(pid, {"tipo": "derrubar", "pid": pid})
            return

        processo = self.buscar_processo(pid)

        if processo:
            processo.ativo = False

            print(f"\nProcesso {pid} caiu.")

            self.enviar_para_todos({"tipo": "estado_processo", "pid": pid, "ativo": False})

            if (
                self.coordenador
                and self.coordenador.pid == pid
            ):
                print("O coordenador ficou indisponível.")

                ativos = [
                    p for p in self.processos
                    if p.ativo
                ]

                if ativos:
                    iniciador = random.choice(ativos)

                    print(
                        f"Processo {iniciador.pid} detectou a falha."
                    )

                    self.iniciar_eleicao(
                        iniciador.pid
                    )

    def reativar_processo(self, pid):
        if not self.eh_local(pid):
            self.enviar_para_dono(pid, {"tipo": "reativar", "pid": pid})
            return

        processo = self.buscar_processo(pid)

        if processo:
            processo.ativo = True

            print(f"\nProcesso {pid} voltou.")

            self.enviar_para_todos({"tipo": "estado_processo", "pid": pid, "ativo": True})

            self.iniciar_eleicao(pid)

    def iniciar_eleicao(self, pid):
        self.atualizar_remotos()

        with self.lock:
            iniciador = self.buscar_processo(pid)

            if not iniciador or not iniciador.ativo:
                return

            print(
                f"\nProcesso {pid} iniciou a eleição."
            )

            superiores = [
                p
                for p in self.processos
                if p.pid > pid and p.ativo
            ]

            if not superiores:
                self.definir_novo_coordenador(iniciador)
                return

            for processo in superiores:
                print(
                    f"Processo {processo.pid} respondeu."
                )

            maior = max(
                superiores,
                key=lambda p: p.pid
            )

        self.iniciar_eleicao(maior.pid)

    def definir_novo_coordenador(self, vencedor):
        with self.lock:
            self.coordenador = vencedor

            print(
                f"Processo {vencedor.pid} virou o coordenador."
            )

        self.enviar_para_todos({"tipo": "coordenador", "pid": vencedor.pid})

    def eh_local(self, pid):
        return not self.local_ids or pid in self.local_ids

    def dono_do_pid(self, pid):
        return self.peers.get(pid)

    def enviar_para_dono(self, pid, mensagem):
        peer = self.dono_do_pid(pid)

        if not peer:
            print(f"Nenhum peer configurado para o processo {pid}.")
            return None

        resposta = enviar_mensagem(peer[0], peer[1], mensagem)

        if resposta is None:
            self.marcar_peer_inativo(peer)
            print(f"Peer {peer[0]}:{peer[1]} não respondeu.")

        return resposta

    def enviar_para_todos(self, mensagem):
        visitados = set()

        for peer in self.peers.values():
            if peer in visitados:
                continue

            visitados.add(peer)
            enviar_mensagem(peer[0], peer[1], mensagem)

    def atualizar_remotos(self):
        visitados = set()

        for peer in self.peers.values():
            if peer in visitados:
                continue

            visitados.add(peer)
            resposta = enviar_mensagem(peer[0], peer[1], {"tipo": "estado"})

            if resposta is None:
                self.marcar_peer_inativo(peer)
                continue

            for item in resposta.get("processos", []):
                processo = self.buscar_processo(item["pid"])

                if processo:
                    processo.ativo = item["ativo"]

            coordenador = resposta.get("coordenador")

            if coordenador is not None:
                processo = self.buscar_processo(coordenador)

                if processo:
                    self.coordenador = processo

    def marcar_peer_inativo(self, peer):
        with self.lock:
            for pid, destino in self.peers.items():
                if destino == peer:
                    processo = self.buscar_processo(pid)

                    if processo:
                        processo.ativo = False

    def estado_local(self):
        with self.lock:
            return {
                "processos": [
                    {"pid": p.pid, "ativo": p.ativo}
                    for p in self.processos
                    if self.eh_local(p.pid)
                ],
                "coordenador": self.coordenador.pid if self.coordenador else None,
            }

    def aplicar_estado_processo(self, pid, ativo):
        processo = self.buscar_processo(pid)

        if processo:
            processo.ativo = ativo

    def aplicar_coordenador(self, pid):
        processo = self.buscar_processo(pid)

        if processo:
            self.coordenador = processo


class ServidorValentao(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, sistema):
        super().__init__(server_address, RequestHandlerClass)
        self.sistema = sistema


class ManipuladorValentao(socketserver.StreamRequestHandler):
    def handle(self):
        linha = self.rfile.readline()

        if not linha:
            return

        mensagem = json.loads(linha.decode("utf-8"))
        resposta = self.processar(mensagem)
        self.wfile.write((json.dumps(resposta) + "\n").encode("utf-8"))

    def processar(self, mensagem):
        sistema = self.server.sistema
        tipo = mensagem.get("tipo")

        if tipo == "estado":
            return sistema.estado_local()

        if tipo == "derrubar":
            sistema.derrubar_processo(mensagem["pid"])
            return {"ok": True}

        if tipo == "reativar":
            sistema.reativar_processo(mensagem["pid"])
            return {"ok": True}

        if tipo == "estado_processo":
            sistema.aplicar_estado_processo(mensagem["pid"], mensagem["ativo"])
            return {"ok": True}

        if tipo == "coordenador":
            sistema.aplicar_coordenador(mensagem["pid"])
            return {"ok": True}

        if tipo == "eleicao":
            sistema.iniciar_eleicao(mensagem["pid"])
            return {"ok": True}

        return {"ok": False, "erro": "tipo desconhecido"}


def enviar_mensagem(host, port, mensagem, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout) as conexao:
            arquivo = conexao.makefile("rwb")
            arquivo.write((json.dumps(mensagem) + "\n").encode("utf-8"))
            arquivo.flush()

            linha = arquivo.readline()

            if not linha:
                return None

            return json.loads(linha.decode("utf-8"))
    except OSError:
        return None


def parse_ids(valor):
    return [int(pid.strip()) for pid in valor.split(",") if pid.strip()]


def parse_peer(valor):
    partes = valor.split(":")

    if len(partes) != 3:
        raise argparse.ArgumentTypeError(
            "use HOST:PORTA:IDS, por exemplo 192.168.0.20:5002:5,6,7"
        )

    host, porta, ids = partes
    return host, int(porta), parse_ids(ids)


def montar_sistema(args):
    local_ids = parse_ids(args.ids)
    peers = {}
    todos_ids = set(local_ids)

    for host, porta, ids in args.peer:
        for pid in ids:
            peers[pid] = (host, porta)
            todos_ids.add(pid)

    sistema = Valentao(local_ids=local_ids, peers=peers)

    for pid in sorted(todos_ids):
        sistema.adicionar_processo(
            Processo(pid)
        )

    sistema.atualizar_remotos()
    sistema.definir_coordenador_inicial()
    sistema.enviar_para_todos({"tipo": "coordenador", "pid": sistema.coordenador.pid})

    return sistema


def iniciar_servidor(sistema, host, porta):
    servidor = ServidorValentao((host, porta), ManipuladorValentao, sistema)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()

    return servidor


def prompt(sistema):
    comandos = "estado | cair PID | voltar PID | eleicao PID | sync | sair"
    print(f"Comandos: {comandos}")

    while True:
        try:
            entrada = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not entrada:
            continue

        partes = entrada.split()
        comando = partes[0].lower()

        if comando in ("sair", "exit", "quit"):
            break

        if comando == "estado":
            sistema.atualizar_remotos()
            sistema.mostrar_estado()
            continue

        if comando == "sync":
            sistema.atualizar_remotos()
            print("Estado sincronizado.")
            continue

        if len(partes) != 2 or comando not in ("cair", "voltar", "eleicao"):
            print(f"Comando inválido. Use: {comandos}")
            continue

        try:
            pid = int(partes[1])
        except ValueError:
            print("PID precisa ser um número.")
            continue

        if comando == "cair":
            sistema.derrubar_processo(pid)
        elif comando == "voltar":
            sistema.reativar_processo(pid)
        elif comando == "eleicao":
            sistema.iniciar_eleicao(pid)


def main_local():
    sistema = Valentao()

    for pid in range(1, 8):
        sistema.adicionar_processo(
            Processo(pid)
        )

    sistema.definir_coordenador_inicial()

    sistema.mostrar_estado()

    # Derruba 7
    sistema.derrubar_processo(7)

    sistema.mostrar_estado()

    # Reativa 7
    sistema.reativar_processo(7)

    sistema.mostrar_estado()


def main_distribuido(args):
    sistema = montar_sistema(args)
    servidor = iniciar_servidor(sistema, args.host, args.port)

    print(f"Nó ouvindo em {args.host}:{args.port}")
    print(f"IDs locais: {sorted(sistema.local_ids)}")
    sistema.mostrar_estado()

    try:
        prompt(sistema)
    finally:
        servidor.shutdown()
        servidor.server_close()


def main():
    parser = argparse.ArgumentParser(
        description="Simulação local ou distribuída do algoritmo do valentão."
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int)
    parser.add_argument("--ids")
    parser.add_argument(
        "--peer",
        action="append",
        default=[],
        type=parse_peer,
        help="Peer no formato HOST:PORTA:IDS. Ex.: 192.168.0.20:5002:5,6,7",
    )

    args = parser.parse_args()

    if args.ids or args.port:
        if not args.ids or not args.port:
            parser.error("modo distribuído precisa de --ids e --port")

        main_distribuido(args)
    else:
        main_local()


if __name__ == "__main__":
    main()
