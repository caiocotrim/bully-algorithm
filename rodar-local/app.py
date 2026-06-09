import random


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
        self.coordenador = None

    def adicionar_processo(self, processo):
        self.processos.append(processo)

    def buscar_processo(self, pid):
        for processo in self.processos:
            if processo.pid == pid:
                return processo
        return None

    def definir_coordenador_inicial(self):
        ativos = [p for p in self.processos if p.ativo]
        self.coordenador = max(ativos, key=lambda p: p.pid)

    def mostrar_estado(self):
        print("\nProcessos:")

        for processo in sorted(self.processos, key=lambda p: p.pid):
            status = "Ativo" if processo.ativo else "Inativo"

            if (
                self.coordenador
                and processo.pid == self.coordenador.pid
                and processo.ativo
            ):
                print(f"{processo.pid} - {status} (Coordenador)")
            else:
                print(f"{processo.pid} - {status}")

        print()

    def derrubar_processo(self, pid):
        processo = self.buscar_processo(pid)

        if processo:
            processo.ativo = False

            print(f"\nProcesso {pid} caiu.")

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
        processo = self.buscar_processo(pid)

        if processo:
            processo.ativo = True

            print(f"\nProcesso {pid} voltou.")

            self.iniciar_eleicao(pid)

    def iniciar_eleicao(self, pid):
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
        self.coordenador = vencedor

        print(
            f"Processo {vencedor.pid} virou o coordenador."
        )


def main():
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


if __name__ == "__main__":
    main()