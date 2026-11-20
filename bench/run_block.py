"""Executa UM bloco do experimento (um runner) e grava os resultados em CSV.

Uso: python bench/run_block.py --bloco 1 --modo piloto --saida saida/bloco-1

Roda num Python "hospedeiro" que tem o pyperformance instalado (bench/requirements.txt).
Os interpretadores medidos são localizados com `uv python find` (instalados antes com `uv python install`).

Saídas em --saida:
  ambiente.json   máquina, sistema e cada interpretador (versão exata e se a GIL está ativa)
  st.csv          cargas de uma thread (pyperformance): uma linha por valor medido pelo pyperf
  mt.csv          cargas com várias threads: uma linha por execução
  log.txt         saída dos comandos, para diagnóstico
"""
import argparse
import csv
import json
import os
import platform
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import config  # noqa: E402

COLS_ST = ["bloco", "interp", "versao", "compilacao", "ordem_interp", "benchmark", "valor_idx", "tempo_s"]
COLS_MT = ["bloco", "interp", "versao", "compilacao", "ordem", "carga", "threads", "repeticao", "escala",
           "unidades", "tempo_s", "checksum", "rss_mb", "gil_ativa", "erro", "timestamp_utc"]


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Log:
    def __init__(self, caminho: Path):
        self.f = caminho.open("a", encoding="utf-8")

    def __call__(self, msg: str) -> None:
        linha = f"[{agora()}] {msg}"
        print(linha, flush=True)
        self.f.write(linha + "\n")
        self.f.flush()


def achar_python(interp: str) -> str:
    r = subprocess.run(["uv", "python", "find", "--no-project", interp], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def info_interpretador(caminho: str) -> dict:
    codigo = ("import json,sys,sysconfig;"
              "f=getattr(sys,'_is_gil_enabled',None);"
              "print(json.dumps({'versao_completa':sys.version,'gil_ativa':True if f is None else f(),"
              "'py_gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'),"
              "'config_args':sysconfig.get_config_var('CONFIG_ARGS')}))")
    r = subprocess.run([caminho, "-c", codigo], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def ler_arquivo(caminho: str) -> str:
    try:
        return Path(caminho).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def info_maquina() -> dict:
    cpuinfo = ler_arquivo("/proc/cpuinfo")
    modelo = next((l.split(":", 1)[1].strip() for l in cpuinfo.splitlines() if l.startswith("model name")),
                  platform.processor())
    meminfo = ler_arquivo("/proc/meminfo")
    mem_kb = next((int(l.split()[1]) for l in meminfo.splitlines() if l.startswith("MemTotal")), None)
    return {
        "cpu_modelo": modelo,
        "n_cpus": os.cpu_count(),
        "mem_gb": round(mem_kb / 1024 / 1024, 1) if mem_kb else None,
        "sistema": platform.platform(),
        "kernel": platform.release(),
        "runner_nome": os.environ.get("RUNNER_NAME"),
        "runner_imagem": os.environ.get("ImageOS"),
        "runner_imagem_versao": os.environ.get("ImageVersion"),
        "python_hospedeiro": sys.version.split()[0],
    }


def rodar_pyperformance(bloco, interp, caminho, ordem, benchmarks, args_modo, saida: Path, trabalho: Path,
                        log: Log) -> list[dict]:
    import pyperf

    destino = (saida / f"pyperf_{interp}.json").resolve()
    destino.unlink(missing_ok=True)
    cmd = [sys.executable, "-m", "pyperformance", "run", "--python", caminho,
           "-b", ",".join(benchmarks), "-o", str(destino), *args_modo]
    log(f"[st] {interp}: {' '.join(cmd)}")
    t0 = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=trabalho)  # os venvs do pyperformance ficam aqui
    log(f"[st] {interp}: código {r.returncode} em {time.monotonic() - t0:.0f} s")
    (saida / f"pyperformance_{interp}.log").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr, encoding="utf-8")
    if not destino.exists():
        log(f"[st] {interp}: SEM RESULTADO (veja pyperformance_{interp}.log)")
        return []

    linhas = []
    for bench in pyperf.BenchmarkSuite.load(str(destino)).get_benchmarks():
        for i, valor in enumerate(bench.get_values()):
            linhas.append({"bloco": bloco, "interp": interp, "versao": config.versao(interp),
                           "compilacao": config.compilacao(interp), "ordem_interp": ordem,
                           "benchmark": bench.get_name(), "valor_idx": i, "tempo_s": valor})
    log(f"[st] {interp}: {len({l['benchmark'] for l in linhas})} benchmarks, {len(linhas)} valores")
    return linhas


def rodar_mt(bloco, tarefas, caminhos, escala, log: Log) -> list[dict]:
    script = str(AQUI / "mt_workloads.py")
    linhas = []
    for ordem, (interp, carga, n_threads, rep) in enumerate(tarefas):
        base = {"bloco": bloco, "interp": interp, "versao": config.versao(interp),
                "compilacao": config.compilacao(interp), "ordem": ordem, "carga": carga,
                "threads": n_threads, "repeticao": rep, "escala": escala, "timestamp_utc": agora()}
        cmd = [caminhos[interp], script, "--carga", carga, "--threads", str(n_threads), "--escala", str(escala)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=config.TIMEOUT_MT_S, check=True)
            res = json.loads(r.stdout.strip().splitlines()[-1])
            linhas.append({**base, **{k: res[k] for k in ("unidades", "tempo_s", "checksum", "rss_mb", "gil_ativa")},
                           "erro": ""})
        except Exception as e:  # registra a falha e segue: a validação decide se o bloco presta
            detalhe = getattr(e, "stderr", "") or str(e)
            linhas.append({**base, "erro": f"{type(e).__name__}: {detalhe.strip()[-300:]}"})
            log(f"[mt] ERRO {interp} {carga} t={n_threads} rep={rep}: {type(e).__name__}")
        if (ordem + 1) % 50 == 0:
            log(f"[mt] {ordem + 1}/{len(tarefas)} execuções")
    return linhas


def gravar_csv(caminho: Path, colunas: list[str], linhas: list[dict]) -> None:
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows não é UTF-8
    p = argparse.ArgumentParser()
    p.add_argument("--bloco", type=int, required=True)
    p.add_argument("--modo", choices=sorted(config.MODOS), required=True)
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--interpretadores", nargs="*", default=config.INTERPRETADORES)
    p.add_argument("--pular-st", action="store_true", help="não roda o pyperformance (útil para testes locais)")
    a = p.parse_args()

    a.saida.mkdir(parents=True, exist_ok=True)
    log = Log(a.saida / "log.txt")
    modo = config.MODOS[a.modo]
    rng = random.Random(config.SEMENTE_BASE + a.bloco)
    inicio = time.monotonic()

    caminhos = {i: achar_python(i) for i in a.interpretadores}
    ambiente = {"bloco": a.bloco, "modo": a.modo, "semente": config.SEMENTE_BASE + a.bloco, "inicio_utc": agora(),
                "maquina": info_maquina(), "pyperformance": config.PYPERFORMANCE_VERSAO,
                "interpretadores": {i: {"caminho": c, **info_interpretador(c)} for i, c in caminhos.items()}}
    log(f"bloco {a.bloco}, modo {a.modo}, CPU {ambiente['maquina']['cpu_modelo']} ({ambiente['maquina']['n_cpus']} vCPUs)")

    # 1) Uma thread: pyperformance, um interpretador por vez, em ordem sorteada.
    linhas_st = []
    ordem_st = rng.sample(a.interpretadores, len(a.interpretadores))
    ambiente["ordem_st"] = ordem_st
    if not a.pular_st:
        benchmarks = config.benchmarks_do_modo(a.modo)
        trabalho = a.saida.resolve().parent / f"_trabalho-bloco-{a.bloco}"  # fora de --saida: não vai para o artifact
        trabalho.mkdir(parents=True, exist_ok=True)
        for ordem, interp in enumerate(ordem_st):
            linhas_st += rodar_pyperformance(a.bloco, interp, caminhos[interp], ordem, benchmarks,
                                             modo["pyperf_args"], a.saida, trabalho, log)
    gravar_csv(a.saida / "st.csv", COLS_ST, linhas_st)

    # 2) Várias threads: todas as combinações embaralhadas juntas (interpretador × carga × threads × repetição).
    tarefas = [(i, c, t, r) for i in a.interpretadores for c in config.CARGAS_MT
               for t in config.THREADS for r in range(modo["mt_reps"])]
    rng.shuffle(tarefas)
    log(f"[mt] {len(tarefas)} execuções")
    linhas_mt = rodar_mt(a.bloco, tarefas, caminhos, modo["mt_escala"], log)
    gravar_csv(a.saida / "mt.csv", COLS_MT, linhas_mt)

    ambiente["fim_utc"] = agora()
    ambiente["duracao_min"] = round((time.monotonic() - inicio) / 60, 1)
    (a.saida / "ambiente.json").write_text(json.dumps(ambiente, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"fim do bloco em {ambiente['duracao_min']} min")


if __name__ == "__main__":
    main()
