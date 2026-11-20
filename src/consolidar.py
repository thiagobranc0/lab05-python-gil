"""Junta os artifacts dos blocos de uma execução e grava o dataset versionado.

Uso: python src/consolidar.py --entrada artefatos --execucao 20261120-2200_piloto_123 --modo piloto

Entrada: artefatos/bloco-*/{st.csv, mt.csv, ambiente.json, log.txt, pyperformance_*.log}
Saída:   data/raw/<execucao>/bloco-N/...      cópia fiel do que cada runner produziu
         data/processed/<execucao>/st.csv     uma thread, todos os blocos
         data/processed/<execucao>/mt.csv     várias threads, todos os blocos
         data/processed/<execucao>/ambiente.csv  uma linha por bloco
         data/execucoes.csv                   índice de todas as execuções (atualizado por src/validar.py)
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
COPIAR = ["st.csv", "mt.csv", "ambiente.json", "log.txt"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows não é UTF-8
    p = argparse.ArgumentParser()
    p.add_argument("--entrada", type=Path, required=True)
    p.add_argument("--execucao", required=True)
    p.add_argument("--modo", required=True)
    a = p.parse_args()

    raw = RAIZ / "data" / "raw" / a.execucao
    proc = RAIZ / "data" / "processed" / a.execucao
    raw.mkdir(parents=True, exist_ok=True)
    proc.mkdir(parents=True, exist_ok=True)

    sts, mts, ambs = [], [], []
    blocos = sorted(d for d in a.entrada.glob("bloco-*") if d.is_dir())
    for d in blocos:
        destino = raw / d.name
        destino.mkdir(exist_ok=True)
        for nome in COPIAR + [f.name for f in d.glob("pyperformance_*.log")]:
            if (d / nome).exists():
                shutil.copy2(d / nome, destino / nome)
        if (d / "st.csv").exists():
            sts.append(pd.read_csv(d / "st.csv"))
        if (d / "mt.csv").exists():
            mts.append(pd.read_csv(d / "mt.csv"))
        if (d / "ambiente.json").exists():
            amb = json.loads((d / "ambiente.json").read_text(encoding="utf-8"))
            linha = {"bloco": amb["bloco"], "modo": amb["modo"], "inicio_utc": amb["inicio_utc"],
                     "fim_utc": amb.get("fim_utc"), "duracao_min": amb.get("duracao_min"), **amb["maquina"]}
            for interp, info in amb["interpretadores"].items():
                linha[f"versao_{interp}"] = info["versao_completa"].split()[0]
                linha[f"gil_{interp}"] = info["gil_ativa"]
            ambs.append(linha)

    vazio = pd.DataFrame()
    (pd.concat(sts, ignore_index=True) if sts else vazio).to_csv(proc / "st.csv", index=False)
    (pd.concat(mts, ignore_index=True) if mts else vazio).to_csv(proc / "mt.csv", index=False)
    pd.DataFrame(ambs).to_csv(proc / "ambiente.csv", index=False)
    (proc / "execucao.json").write_text(json.dumps(
        {"execucao": a.execucao, "modo": a.modo, "blocos_com_artifact": [d.name for d in blocos]},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{a.execucao}: {len(blocos)} blocos, {sum(map(len, sts))} valores st, {sum(map(len, mts))} execuções mt")


if __name__ == "__main__":
    main()
