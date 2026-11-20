"""Cargas com várias threads. Roda DENTRO do interpretador medido (só biblioteca padrão).

Uso: <python> bench/mt_workloads.py --carga cpu_puro --threads 4 [--escala 1.0]
Imprime uma linha JSON com o tempo, o pico de memória e se a GIL estava ativa.

Desenho de "escala forte": o trabalho TOTAL é fixo e é dividido igualmente entre as threads.
Se as threads rodam em paralelo de verdade, o tempo cai com mais threads; com a GIL, não cai
(a não ser na carga de controle, que libera a GIL sozinha).
"""
import argparse
import hashlib
import json
import sys
import threading
import time

# Quantidade de trabalho com escala 1.0, calibrada para ~1–2 s com 1 thread num runner do GitHub.
TRABALHO = {
    "cpu_puro": 12_000,       # nº de blocos de 50 números testados por divisão
    "json": 48_000,           # nº de ciclos dumps+loads
    "hash_controle": 800,     # nº de SHA-256 de 4 MiB
}

DOC_JSON = {
    "id": 12345, "nome": "experimento", "ativo": True, "nota": 9.5,
    "tags": ["python", "gil", "benchmark", "threads"] * 4,
    "itens": [{"sku": f"item-{i}", "qtd": i, "preco": i * 1.25, "obs": None} for i in range(30)],
}
BUFFER = bytes(range(256)) * (4 * 1024 * 1024 // 256)


def eh_primo(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def tarefa_cpu_puro(inicio: int, fim: int) -> int:
    total = 0
    for bloco in range(inicio, fim):
        base = 1_000_000 + bloco * 50
        for n in range(base, base + 50):
            if eh_primo(n):
                total += 1
    return total


def tarefa_json(inicio: int, fim: int) -> int:
    total = 0
    for _ in range(inicio, fim):
        total += len(json.loads(json.dumps(DOC_JSON))["itens"])
    return total


def tarefa_hash(inicio: int, fim: int) -> int:
    total = 0
    for _ in range(inicio, fim):
        total += hashlib.sha256(BUFFER).digest()[0]
    return total


TAREFAS = {"cpu_puro": tarefa_cpu_puro, "json": tarefa_json, "hash_controle": tarefa_hash}


def gil_ativa() -> bool:
    f = getattr(sys, "_is_gil_enabled", None)
    return True if f is None else bool(f())


def pico_rss_mb():
    try:
        import resource  # só existe em Unix
    except ImportError:
        return None
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux: KiB -> MiB


def medir(carga: str, n_threads: int, escala: float) -> dict:
    tarefa = TAREFAS[carga]
    total = max(n_threads, int(TRABALHO[carga] * escala))

    # Aquecimento (não medido): 2% do trabalho numa thread só.
    tarefa(0, max(1, total // 50))

    # Fatias iguais do trabalho total, uma por thread.
    limites = [total * i // n_threads for i in range(n_threads + 1)]
    resultados = [0] * n_threads
    largada = threading.Barrier(n_threads + 1)

    def trabalhador(i: int) -> None:
        largada.wait()
        resultados[i] = tarefa(limites[i], limites[i + 1])

    threads = [threading.Thread(target=trabalhador, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    largada.wait()  # todas as threads prontas: dispara o cronômetro
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    tempo = time.perf_counter() - t0

    return {
        "carga": carga,
        "threads": n_threads,
        "escala": escala,
        "unidades": total,
        "tempo_s": tempo,
        "checksum": sum(resultados),  # o mesmo trabalho tem de dar o mesmo resultado em todo interpretador
        "rss_mb": pico_rss_mb(),
        "gil_ativa": gil_ativa(),
        "versao_python": sys.version.split()[0],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--carga", choices=sorted(TAREFAS), required=True)
    p.add_argument("--threads", type=int, required=True)
    p.add_argument("--escala", type=float, default=1.0)
    a = p.parse_args()
    print(json.dumps(medir(a.carga, a.threads, a.escala)))


if __name__ == "__main__":
    main()
