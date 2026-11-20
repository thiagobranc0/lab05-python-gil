"""Configuração única do experimento. Toda mudança de desenho acontece aqui (e é registrada em bench/DESENHO.md)."""

# Interpretadores comparados: versão × compilação. O sufixo "t" é a compilação free-threaded (sem GIL).
# São instalados com `uv python install`, igual no GitHub Actions e numa máquina local.
INTERPRETADORES = ["3.13", "3.13t", "3.14", "3.14t", "3.15", "3.15t"]

# A versão do uv define QUAIS builds existem para cada "3.x". Fixá-la (no workflow: setup-uv `version`)
# garante que todos os runners instalem exatamente as mesmas versões. A validação confere VERSOES_ESPERADAS.
UV_VERSAO = "0.13.9"  # lançado em 17/11/2026; manter igual ao .github/workflows/benchmark.yml
VERSOES_ESPERADAS = {"3.13": "3.13.18", "3.14": "3.14.10", "3.15": "3.15.2"}  # finais, conferidas em 20/11/2026

# Versão do pyperformance (a suíte oficial de benchmarks do CPython). Fixada para o estudo ser reprodutível.
PYPERFORMANCE_VERSAO = "1.14.0"

# Subconjunto do pyperformance para as cargas de UMA thread (Q1 e Q2).
# Critério de inclusão: benchmark em Python puro, sem dependência de terceiros com extensão em C,
# para rodar igual nas compilações com e sem GIL. Benchmarks removidos depois do piloto ficam
# listados em EXCLUIDOS, com o motivo.
BENCHMARKS_PYPERF = [
    "chaos", "comprehensions", "coroutines", "deepcopy", "deltablue",
    "fannkuch", "float", "generators", "go", "hexiom",
    "json_dumps", "json_loads", "nbody", "nqueens", "pickle_pure_python",
    "pidigits", "raytrace", "regex_compile", "richards", "spectral_norm",
]
EXCLUIDOS: dict[str, str] = {}  # nome -> motivo (preenchido a partir do relatório de validação do piloto)

# Cargas próprias com VÁRIAS threads (Q3 e Q4), em bench/mt_workloads.py.
#   cpu_puro       Python puro, CPU-bound: a GIL deveria impedir ganho com mais threads.
#   json           serialização/desserialização: também segura a GIL na maior parte do tempo.
#   hash_controle  hashlib em buffers grandes: a GIL já é liberada, então ter ou não GIL NÃO
#                  deveria mudar o resultado. É o grupo de controle das cargas com threads.
CARGAS_MT = ["cpu_puro", "json", "hash_controle"]
THREADS = [1, 2, 4]

# Semente: a ordem dos tratamentos dentro de cada bloco é sorteada com SEMENTE_BASE + nº do bloco.
SEMENTE_BASE = 20261120

# Modos de execução (escolhidos ao disparar o workflow).
#   teste    fumaça: confere que tudo roda; dados descartáveis.
#   piloto   calibra repetições e blocos; detecta benchmarks que não rodam.
#   completo dataset do estudo.
MODOS = {
    "teste": {"pyperf_args": ["--debug-single-value"], "n_benchmarks": 3, "mt_reps": 1, "mt_escala": 0.05},
    "piloto": {"pyperf_args": ["--fast"], "n_benchmarks": None, "mt_reps": 3, "mt_escala": 1.0},
    "completo": {"pyperf_args": [], "n_benchmarks": None, "mt_reps": 10, "mt_escala": 1.0},
}

# Limites da validação automática (src/validar.py).
LIMITE_CV = 0.10            # coeficiente de variação acima disso numa célula = aviso de instabilidade
LIMITE_CELULAS_INSTAVEIS = 0.25  # fração de células instáveis acima disso = aviso forte no relatório
LIMITE_FALTANTES_MT = 0.05  # fração de medições com threads faltando acima disso = erro
TIMEOUT_MT_S = 300          # tempo máximo de uma execução de carga com threads


def benchmarks_do_modo(modo: str) -> list[str]:
    lista = [b for b in BENCHMARKS_PYPERF if b not in EXCLUIDOS]
    n = MODOS[modo]["n_benchmarks"]
    return lista[:n] if n else lista


def compilacao(interp: str) -> str:
    return "free-threaded" if interp.endswith("t") else "padrao"


def versao(interp: str) -> str:
    return interp.rstrip("t")
