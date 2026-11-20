"""Validação AUTOMÁTICA de uma execução. Roda no workflow; ninguém valida dados à mão.

Uso: python src/validar.py --execucao <id> --blocos-esperados 8

Gera data/processed/<execucao>/VALIDACAO.md e validacao.json e atualiza data/execucoes.csv.
Código de saída 1 se houver ERRO: o workflow então falha e abre uma issue com o relatório.

ERRO  = o dado não serve para a análise (falta bloco/interpretador, GIL no estado errado,
        trabalho diferente entre interpretadores, tempos impossíveis, benchmark faltando no modo completo).
AVISO = o dado serve, mas merece atenção (instabilidade, CPUs diferentes, benchmark a excluir no piloto).
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "bench"))
import config  # noqa: E402


class Relatorio:
    def __init__(self):
        self.erros, self.avisos, self.infos = [], [], []
        self.excluir: dict[str, str] = {}

    def erro(self, m):
        self.erros.append(m)

    def aviso(self, m):
        self.avisos.append(m)

    def info(self, m):
        self.infos.append(m)


def ler(caminho: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(caminho)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def validar_ambiente(amb: pd.DataFrame, esperados: int, modo: str, r: Relatorio) -> None:
    if amb.empty:
        r.erro("Nenhum bloco gravou `ambiente.json`: nenhum runner terminou.")
        return
    if len(amb) < esperados:
        r.erro(f"Só {len(amb)} de {esperados} blocos terminaram.")
    for interp in config.INTERPRETADORES:
        col = f"gil_{interp}"
        if col not in amb:
            r.erro(f"Interpretador {interp} ausente no ambiente.")
            continue
        esperado = config.compilacao(interp) == "padrao"
        errados = amb.loc[amb[col].astype(str).str.lower() != str(esperado).lower(), "bloco"].tolist()
        if errados:
            r.erro(f"{interp}: GIL {'desligada' if esperado else 'ligada'} nos blocos {errados} "
                   f"(esperado: {'ligada' if esperado else 'desligada'}). O interpretador instalado não é o pretendido.")
        versoes = amb.get(f"versao_{interp}", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
        pre = [v for v in versoes if not re.fullmatch(r"\d+\.\d+\.\d+", v)]
        if pre:
            msg = (f"{interp}: versão que não é final ({pre}): alfa, beta ou rc não é a versão que roda em produção. "
                   "Atualize o uv (que define quais builds existem) no workflow.")
            r.erro(msg) if modo == "completo" else r.aviso(msg)
        esperada = config.VERSOES_ESPERADAS.get(config.versao(interp))
        if esperada and versoes and versoes != [esperada]:
            msg = (f"{interp}: instalada {versoes}, esperada {esperada} (uv {config.UV_VERSAO}). "
                   "Confira se a versão do uv no workflow é a mesma de bench/config.py.")
            r.erro(msg) if modo == "completo" else r.aviso(msg)
        if len(versoes) > 1:
            r.aviso(f"{interp}: versões exatas diferentes entre blocos: {versoes}.")
        elif versoes:
            r.info(f"{interp}: {versoes[0]}")
    cpus = amb["cpu_modelo"].value_counts().to_dict()
    r.info(f"Modelos de CPU por bloco: {cpus}")
    if len(cpus) > 1:
        r.aviso(f"Os blocos rodaram em {len(cpus)} modelos de CPU diferentes. Esperado em runners do GitHub; "
                "a análise trata o bloco como fator, então a comparação entre interpretadores continua pareada.")
    if "duracao_min" in amb:
        r.info(f"Duração dos blocos: {amb['duracao_min'].min():.0f}–{amb['duracao_min'].max():.0f} min")


def validar_st(st: pd.DataFrame, modo: str, r: Relatorio) -> None:
    if st.empty:
        r.erro("Nenhum resultado do pyperformance (uma thread).")
        return
    if (st["tempo_s"] <= 0).any() or st["tempo_s"].isna().any():
        r.erro("Há tempos ≤ 0 ou vazios nos resultados de uma thread.")

    blocos = sorted(st["bloco"].unique())
    for b in blocos:
        faltam = set(config.INTERPRETADORES) - set(st.loc[st["bloco"] == b, "interp"])
        if faltam:
            r.erro(f"Bloco {b}: pyperformance sem resultado para {sorted(faltam)}.")

    # Benchmark presente em todos os interpretadores de todos os blocos?
    presenca = st.groupby(["benchmark", "interp"])["bloco"].nunique().unstack(fill_value=0)
    presenca = presenca.reindex(columns=config.INTERPRETADORES, fill_value=0)
    incompletos = presenca[(presenca < len(blocos)).any(axis=1)]
    for bench, linha in incompletos.iterrows():
        sem = [i for i in config.INTERPRETADORES if linha[i] < len(blocos)]
        msg = f"Benchmark `{bench}` faltou em {sem}."
        if modo == "completo":
            r.erro(msg)
        else:
            r.aviso(msg + " Sugestão: excluir do desenho.")
            r.excluir[bench] = f"não rodou em {', '.join(sem)} no piloto"
    r.info(f"{presenca.shape[0] - len(incompletos)} benchmarks completos em todos os interpretadores.")

    # Estabilidade: coeficiente de variação dos valores do pyperf em cada célula (bloco × interp × benchmark).
    cv = st.groupby(["bloco", "interp", "benchmark"])["tempo_s"].agg(lambda x: x.std(ddof=1) / x.mean()
                                                                     if len(x) > 1 else np.nan).dropna()
    if len(cv):
        frac = (cv > config.LIMITE_CV).mean()
        r.info(f"Uma thread: CV mediano {cv.median():.1%}; {frac:.0%} das células acima de {config.LIMITE_CV:.0%}.")
        if frac > config.LIMITE_CELULAS_INSTAVEIS:
            piores = cv.groupby("benchmark").median().sort_values(ascending=False).head(5)
            r.aviso(f"Instabilidade alta: {frac:.0%} das células com CV > {config.LIMITE_CV:.0%}. "
                    f"Benchmarks mais instáveis (CV mediano): "
                    + ", ".join(f"{b} {v:.0%}" for b, v in piores.items()))


def validar_mt(mt: pd.DataFrame, modo: str, n_blocos: int, r: Relatorio) -> None:
    if mt.empty:
        r.erro("Nenhum resultado das cargas com threads.")
        return
    reps = config.MODOS[modo]["mt_reps"]
    esperado = n_blocos * len(config.INTERPRETADORES) * len(config.CARGAS_MT) * len(config.THREADS) * reps
    ok = mt[mt["erro"].isna() | (mt["erro"].astype(str) == "")]
    faltando = 1 - len(ok) / esperado if esperado else 1
    r.info(f"Várias threads: {len(ok)} de {esperado} execuções válidas.")
    if faltando > config.LIMITE_FALTANTES_MT:
        exemplos = mt.loc[~mt.index.isin(ok.index), "erro"].astype(str).str[:150].value_counts().head(3)
        r.erro(f"{faltando:.0%} das execuções com threads falharam ou faltam (limite {config.LIMITE_FALTANTES_MT:.0%}). "
               f"Erros mais comuns: {exemplos.to_dict()}")
    if ok.empty:
        return
    if (ok["tempo_s"] <= 0).any():
        r.erro("Há tempos ≤ 0 nas cargas com threads.")

    # O mesmo trabalho tem de produzir o mesmo checksum em todo interpretador.
    chk = ok.groupby(["carga", "escala"])["checksum"].nunique()
    for (carga, escala), n in chk.items():
        if n > 1:
            r.erro(f"Carga `{carga}`: checksums diferentes entre execuções. Os interpretadores não fizeram o mesmo trabalho.")

    # GIL no estado certo durante a carga (uma extensão C pode religar a GIL na compilação free-threaded).
    gil = ok["gil_ativa"].astype(str).str.lower() == "true"
    errados = ok[gil != (ok["compilacao"] == "padrao")]
    if len(errados):
        r.erro(f"{len(errados)} execuções com a GIL no estado errado, ex.: "
               f"{errados[['interp', 'carga']].drop_duplicates().head(3).to_dict('records')}")

    cv = ok.groupby(["bloco", "interp", "carga", "threads"])["tempo_s"].agg(
        lambda x: x.std(ddof=1) / x.mean() if len(x) > 1 else np.nan).dropna()
    if len(cv):
        frac = (cv > config.LIMITE_CV).mean()
        r.info(f"Várias threads: CV mediano {cv.median():.1%}; {frac:.0%} das células acima de {config.LIMITE_CV:.0%}.")
        if frac > config.LIMITE_CELULAS_INSTAVEIS:
            r.aviso(f"Instabilidade alta nas cargas com threads: {frac:.0%} das células com CV > {config.LIMITE_CV:.0%}.")


def escrever(r: Relatorio, execucao: str, modo: str, destino: Path) -> str:
    status = "falha" if r.erros else "ok"
    secoes = [f"# Validação automática: `{execucao}`", "",
              f"**Status: {'❌ FALHA' if r.erros else '✅ OK'}** · modo `{modo}` · "
              f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", ""]
    for titulo, itens in (("Erros", r.erros), ("Avisos", r.avisos), ("Informações", r.infos)):
        secoes += [f"## {titulo} ({len(itens)})", ""] + ([f"- {i}" for i in itens] or ["- nenhum"]) + [""]
    if r.excluir:
        secoes += ["## Benchmarks sugeridos para exclusão", "",
                   "Copiar para `EXCLUIDOS` em `bench/config.py`:", "", "```python",
                   "EXCLUIDOS = " + json.dumps(r.excluir, ensure_ascii=False, indent=4), "```", ""]
    texto = "\n".join(secoes)
    (destino / "VALIDACAO.md").write_text(texto, encoding="utf-8")
    (destino / "validacao.json").write_text(json.dumps(
        {"execucao": execucao, "modo": modo, "status": status, "erros": r.erros, "avisos": r.avisos,
         "infos": r.infos, "excluir": r.excluir}, indent=2, ensure_ascii=False), encoding="utf-8")
    return status


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows não é UTF-8
    p = argparse.ArgumentParser()
    p.add_argument("--execucao", required=True)
    p.add_argument("--blocos-esperados", type=int, required=True)
    a = p.parse_args()

    proc = RAIZ / "data" / "processed" / a.execucao
    modo = json.loads((proc / "execucao.json").read_text(encoding="utf-8"))["modo"]
    st, mt, amb = ler(proc / "st.csv"), ler(proc / "mt.csv"), ler(proc / "ambiente.csv")

    r = Relatorio()
    validar_ambiente(amb, a.blocos_esperados, modo, r)
    validar_st(st, modo, r)
    validar_mt(mt, modo, len(amb) if not amb.empty else a.blocos_esperados, r)
    status = escrever(r, a.execucao, modo, proc)

    indice = RAIZ / "data" / "execucoes.csv"
    linha = pd.DataFrame([{"execucao": a.execucao, "modo": modo, "status": status, "blocos": len(amb),
                           "erros": len(r.erros), "avisos": len(r.avisos),
                           "validado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}])
    antigo = ler(indice)
    if not antigo.empty:
        antigo = antigo[antigo["execucao"] != a.execucao]
    pd.concat([antigo, linha], ignore_index=True).to_csv(indice, index=False)

    print((proc / "VALIDACAO.md").read_text(encoding="utf-8"))
    sys.exit(1 if status == "falha" else 0)


if __name__ == "__main__":
    main()
