"""Análise estatística do experimento (Q1–Q4). Usada pelo build.py; não grava nada sozinha.

Unidade de análise
- Uma thread (Q1, Q2): o BENCHMARK. Em cada bloco (runner) e interpretador, o tempo de um benchmark é a
  mediana dos valores do pyperf; depois, a média geométrica entre os blocos. Os testes comparam os mesmos
  benchmarks entre interpretadores (pareado).
- Várias threads (Q3, Q4): a execução. ANOVA fatorial sobre log(tempo) com bloco como fator.

Testes
- Wilcoxon pareado (bilateral) sobre a diferença de log(tempo) entre dois interpretadores, por benchmark.
  Tamanho do efeito: correlação rank-biserial pareada (−1 a 1).
- ANOVA (statsmodels, tipo II): log(tempo) ~ compilação × threads + versão + bloco, uma por carga.
  Tamanho do efeito: η² parcial.
- Correção de Holm sobre a família inteira de testes.
- IC 95% por bootstrap (reamostrando benchmarks) para as médias geométricas de razões de tempo.
"""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "bench"))
import config  # noqa: E402

VERSOES = sorted({config.versao(i) for i in config.INTERPRETADORES}, key=lambda v: tuple(map(int, v.split("."))))
SEMENTE_BOOT = 42
N_BOOT = 5000


# ----------------------------------------------------------------------------- dados
def escolher_execucao() -> str | None:
    """Última execução válida, preferindo o modo completo; depois piloto; depois teste."""
    indice = RAIZ / "data" / "execucoes.csv"
    if not indice.exists():
        return None
    ex = pd.read_csv(indice)
    ex = ex[ex["status"] == "ok"]
    for modo in ("completo", "piloto", "teste"):
        candidatas = ex[ex["modo"] == modo].sort_values("validado_utc")
        if len(candidatas):
            return candidatas["execucao"].iloc[-1]
    return None


@dataclass
class Dados:
    execucao: str
    modo: str
    st: pd.DataFrame
    mt: pd.DataFrame
    amb: pd.DataFrame
    validacao: dict


def carregar(execucao: str) -> Dados:
    proc = RAIZ / "data" / "processed" / execucao
    meta = json.loads((proc / "execucao.json").read_text(encoding="utf-8"))
    mt = pd.read_csv(proc / "mt.csv")
    mt = mt[mt["erro"].isna() | (mt["erro"].astype(str) == "")].copy()
    return Dados(execucao, meta["modo"], pd.read_csv(proc / "st.csv"), mt, pd.read_csv(proc / "ambiente.csv"),
                 json.loads((proc / "validacao.json").read_text(encoding="utf-8")))


# ----------------------------------------------------------------------------- utilitários
def gmean(x) -> float:
    x = np.asarray(x, dtype=float)
    return float(np.exp(np.mean(np.log(x))))


def ic_bootstrap_gmean(razoes, n=N_BOOT) -> tuple[float, float]:
    razoes = np.asarray(razoes, dtype=float)
    if len(razoes) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(SEMENTE_BOOT)
    logs = np.log(razoes)
    medias = logs[rng.integers(0, len(logs), size=(n, len(logs)))].mean(axis=1)
    return float(np.exp(np.percentile(medias, 2.5))), float(np.exp(np.percentile(medias, 97.5)))


def wilcoxon_pareado(log_a, log_b) -> dict:
    """Wilcoxon bilateral sobre d = log_b − log_a, com rank-biserial pareado como tamanho do efeito."""
    d = np.asarray(log_b) - np.asarray(log_a)
    d = d[d != 0]
    if len(d) < 5:
        return {"n": len(d), "W": np.nan, "p": np.nan, "rb": np.nan}
    res = stats.wilcoxon(d, alternative="two-sided")
    postos = stats.rankdata(np.abs(d))
    rb = (postos[d > 0].sum() - postos[d < 0].sum()) / postos.sum()
    return {"n": len(d), "W": float(res.statistic), "p": float(res.pvalue), "rb": float(rb)}


def holm(pvals: list[float]) -> list[float]:
    p = np.asarray(pvals, dtype=float)
    ok = ~np.isnan(p)
    ajust = np.full_like(p, np.nan)
    if ok.sum():
        ordem = np.argsort(p[ok])
        m = ok.sum()
        corr = np.minimum(1, np.maximum.accumulate((m - np.arange(m)) * p[ok][ordem]))
        tmp = np.empty(m)
        tmp[ordem] = corr
        ajust[ok] = tmp
    return ajust.tolist()


# ----------------------------------------------------------------------------- uma thread
def tempos_por_benchmark(st: pd.DataFrame) -> pd.DataFrame:
    """Tempo de cada benchmark por interpretador: mediana dentro do bloco, média geométrica entre blocos."""
    por_bloco = st.groupby(["bloco", "interp", "benchmark"])["tempo_s"].median().reset_index()
    t = por_bloco.groupby(["interp", "benchmark"])["tempo_s"].agg(gmean).unstack("interp")
    return t.dropna()  # só benchmarks presentes em todos os interpretadores


@dataclass
class Resultado:
    q1: pd.DataFrame = field(default_factory=pd.DataFrame)       # speedup por benchmark (padrão vs 3.13)
    q1_resumo: pd.DataFrame = field(default_factory=pd.DataFrame)
    q2: pd.DataFrame = field(default_factory=pd.DataFrame)       # razão free-threaded/padrão por benchmark
    q2_resumo: pd.DataFrame = field(default_factory=pd.DataFrame)
    q3: pd.DataFrame = field(default_factory=pd.DataFrame)       # speedup por carga, versão, compilação, threads
    q3_anova: pd.DataFrame = field(default_factory=pd.DataFrame)
    q4: pd.DataFrame = field(default_factory=pd.DataFrame)
    testes: pd.DataFrame = field(default_factory=pd.DataFrame)
    cv_st: pd.DataFrame = field(default_factory=pd.DataFrame)


def analisar_q1(t: pd.DataFrame, testes: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = VERSOES[0]
    q1 = pd.DataFrame({f"{v}": t[base] / t[v] for v in VERSOES[1:]})  # > 1 = mais rápido que a base
    resumo = []
    for v in VERSOES[1:]:
        lo, hi = ic_bootstrap_gmean(q1[v])
        resumo.append({"comparacao": f"{v} × {base}", "speedup_gmean": gmean(q1[v]), "ic_lo": lo, "ic_hi": hi,
                       "mais_rapidos": int((q1[v] > 1).sum()), "n": len(q1)})
    pares = [(VERSOES[i], VERSOES[i + 1]) for i in range(len(VERSOES) - 1)] + [(VERSOES[0], VERSOES[-1])]
    for a, b in pares:
        w = wilcoxon_pareado(np.log(t[a]), np.log(t[b]))
        testes.append({"questao": "Q1", "teste": f"Wilcoxon pareado: tempo {b} × {a} (padrão)", **w})
    return q1, pd.DataFrame(resumo)


def analisar_q2(t: pd.DataFrame, testes: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    q2 = pd.DataFrame({v: t[f"{v}t"] / t[v] for v in VERSOES})  # > 1 = free-threaded mais lento
    resumo = []
    for v in VERSOES:
        lo, hi = ic_bootstrap_gmean(q2[v])
        resumo.append({"versao": v, "razao_gmean": gmean(q2[v]), "ic_lo": lo, "ic_hi": hi,
                       "mais_lentos": int((q2[v] > 1).sum()), "n": len(q2)})
        w = wilcoxon_pareado(np.log(t[v]), np.log(t[f"{v}t"]))
        testes.append({"questao": "Q2", "teste": f"Wilcoxon pareado: tempo {v}t × {v} (1 thread)", **w})
    return q2, pd.DataFrame(resumo)


# ----------------------------------------------------------------------------- várias threads
def analisar_q3(mt: pd.DataFrame, testes: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm

    cel = mt.groupby(["bloco", "versao", "compilacao", "carga", "threads"])["tempo_s"].median().reset_index()
    ref = cel[(cel["compilacao"] == "padrao") & (cel["threads"] == 1)][["bloco", "versao", "carga", "tempo_s"]]
    cel = cel.merge(ref.rename(columns={"tempo_s": "t_ref"}), on=["bloco", "versao", "carga"])
    cel["speedup"] = cel["t_ref"] / cel["tempo_s"]  # relativo à compilação padrão com 1 thread, mesma versão
    q3 = (cel.groupby(["carga", "versao", "compilacao", "threads"])["speedup"]
          .agg(speedup=gmean, n_blocos="count").reset_index())

    linhas = []
    for carga, d in mt.groupby("carga"):
        d = d.assign(log_t=np.log(d["tempo_s"]))
        formula = "log_t ~ C(compilacao) * C(threads) + C(versao)" + (" + C(bloco)" if d["bloco"].nunique() > 1 else "")
        tab = anova_lm(smf.ols(formula, data=d).fit(), typ=2)
        ss_res = tab.loc["Residual", "sum_sq"]
        for efeito in ("C(compilacao)", "C(threads)", "C(compilacao):C(threads)"):
            linha = tab.loc[efeito]
            eta = linha["sum_sq"] / (linha["sum_sq"] + ss_res)
            linhas.append({"carga": carga, "efeito": efeito.replace("C(", "").replace(")", ""),
                           "F": linha["F"], "p": linha["PR(>F)"], "eta2_parcial": eta})
            if efeito == "C(compilacao):C(threads)":
                testes.append({"questao": "Q3", "teste": f"ANOVA, interação compilação × threads: {carga}",
                               "n": len(d), "W": linha["F"], "p": linha["PR(>F)"], "rb": np.nan,
                               "eta2_parcial": eta})
    return q3, pd.DataFrame(linhas)


def analisar_q4(mt: pd.DataFrame) -> pd.DataFrame:
    if mt["rss_mb"].isna().all():
        return pd.DataFrame()
    cel = mt.groupby(["bloco", "versao", "compilacao", "carga", "threads"])["rss_mb"].median().unstack("compilacao")
    cel = cel.dropna()
    cel["razao"] = cel["free-threaded"] / cel["padrao"]
    return (cel.reset_index().groupby(["carga", "threads"])
            .agg(rss_padrao_mb=("padrao", "median"), rss_ft_mb=("free-threaded", "median"), razao=("razao", gmean))
            .reset_index())


def analisar(d: Dados) -> Resultado:
    r = Resultado()
    testes: list[dict] = []
    if not d.st.empty:
        t = tempos_por_benchmark(d.st)
        r.q1, r.q1_resumo = analisar_q1(t, testes)
        r.q2, r.q2_resumo = analisar_q2(t, testes)
        r.cv_st = (d.st.groupby(["bloco", "interp", "benchmark"])["tempo_s"]
                   .agg(lambda x: x.std(ddof=1) / x.mean() if len(x) > 1 else np.nan).dropna()
                   .rename("cv").reset_index())
    if not d.mt.empty:
        r.q3, r.q3_anova = analisar_q3(d.mt, testes)
        r.q4 = analisar_q4(d.mt)
    r.testes = pd.DataFrame(testes)
    if len(r.testes):
        r.testes["p_holm"] = holm(r.testes["p"].tolist())
    return r
