"""Gráficos do README (PNG estáticos; cada gráfico tem a tabela correspondente no README).

Cores: a versão sempre tem a mesma cor (3.13 azul, 3.14 laranja, 3.15 verde-água). Nas cargas com
threads, a série é a compilação: padrão em cinza (referência) e free-threaded em violeta.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e6e5e0"
COR_VERSAO = {"3.13": "#2a78d6", "3.14": "#eb6834", "3.15": "#1baf7a"}
COR_COMPILACAO = {"padrao": "#52514e", "free-threaded": "#6250d6"}
NOME_COMPILACAO = {"padrao": "padrão (com GIL)", "free-threaded": "free-threaded (sem GIL)"}
NOME_CARGA = {"cpu_puro": "CPU em Python puro", "json": "JSON", "hash_controle": "hashlib (controle)"}

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
    "axes.edgecolor": GRADE, "axes.labelcolor": TEXTO_2, "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    "text.color": TEXTO, "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
    "axes.titleweight": "bold", "legend.frameon": False, "lines.linewidth": 2,
})


def virgula(casas=2):
    return FuncFormatter(lambda x, _: f"{x:.{casas}f}".replace(".", ","))


def _salvar(fig, destino: Path) -> str:
    fig.savefig(destino, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return destino.name


def g1_speedup_versoes(q1: pd.DataFrame, destino: Path) -> str:
    """Q1: speedup de cada versão em relação à 3.13, por benchmark (compilação padrão)."""
    ordem = q1[q1.columns[-1]].sort_values().index
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(ordem) + 1.6))
    y = np.arange(len(ordem))
    for v in q1.columns:
        ax.scatter(q1.loc[ordem, v], y, s=55, color=COR_VERSAO.get(v), label=v, zorder=3,
                   edgecolor=SUPERFICIE, linewidth=1.5)
    ax.axvline(1, color=TEXTO_2, linewidth=1, linestyle="--", zorder=2)
    ax.set_yticks(y, ordem)
    ax.xaxis.set_major_locator(MaxNLocator(steps=[1, 2, 5, 10]))
    ax.xaxis.set_major_formatter(virgula())
    ax.set_xlabel("speedup em relação à 3.13 (> 1 = mais rápido)")
    ax.set_title("G1 · Cada versão nova é mais rápida? (uma thread, compilação padrão)", loc="left")
    ax.legend(title="versão", loc="lower right")
    ax.grid(axis="y", visible=False)
    return _salvar(fig, destino)


def g2_custo_free_threaded(q2: pd.DataFrame, resumo: pd.DataFrame, destino: Path) -> str:
    """Q2: razão de tempo free-threaded / padrão por benchmark, com média geométrica e IC 95%."""
    fig, ax = plt.subplots(figsize=(7, 4.2))
    rng = np.random.default_rng(0)
    for i, v in enumerate(q2.columns):
        x = i + rng.uniform(-0.12, 0.12, len(q2))
        ax.scatter(x, q2[v], s=26, color=COR_VERSAO.get(v), alpha=0.55, zorder=3, edgecolor="none")
        linha = resumo.set_index("versao").loc[v]
        ax.errorbar(i + 0.3, linha["razao_gmean"],
                    yerr=[[linha["razao_gmean"] - linha["ic_lo"]], [linha["ic_hi"] - linha["razao_gmean"]]]
                    if not np.isnan(linha["ic_lo"]) else None,
                    fmt="o", ms=9, color=COR_VERSAO.get(v), ecolor=TEXTO_2, elinewidth=2, capsize=4, zorder=4)
        ax.annotate(f"{linha['razao_gmean']:.2f}×".replace(".", ","), (i + 0.42, linha["razao_gmean"]),
                    va="center", color=TEXTO, fontsize=9)
    ax.axhline(1, color=TEXTO_2, linewidth=1, linestyle="--")
    ax.set_xticks(range(len(q2.columns)), [f"{v}t ÷ {v}" for v in q2.columns])
    ax.yaxis.set_major_locator(MaxNLocator(steps=[1, 2, 5, 10]))
    ax.yaxis.set_major_formatter(virgula())
    ax.set_ylabel("tempo sem GIL ÷ tempo com GIL (> 1 = mais lento)")
    ax.set_title("G2 · Quanto custa tirar a GIL em código de uma thread?", loc="left")
    ax.set_xlim(-0.5, len(q2.columns) - 0.2)
    ax.grid(axis="x", visible=False)
    ax.text(0, -0.16, "Pontos: benchmarks. Marcador grande: média geométrica com IC 95% (bootstrap).",
            transform=ax.transAxes, color=TEXTO_2, fontsize=8.5)
    return _salvar(fig, destino)


def g3_escalonamento(q3: pd.DataFrame, destino: Path) -> str:
    """Q3: speedup × nº de threads, padrão × free-threaded, por carga (linhas) e versão (colunas)."""
    cargas = [c for c in NOME_CARGA if c in set(q3["carga"])]
    versoes = sorted(q3["versao"].astype(str).unique())
    threads = sorted(q3["threads"].unique())
    fig, eixos = plt.subplots(len(cargas), len(versoes), figsize=(3.1 * len(versoes), 2.7 * len(cargas)),
                              sharex=True, sharey="row", squeeze=False)
    for i, carga in enumerate(cargas):
        for j, v in enumerate(versoes):
            ax = eixos[i][j]
            ax.plot(threads, threads, color=GRADE, linestyle="--", linewidth=1.5, label="escala ideal")
            for comp in ("padrao", "free-threaded"):
                d = q3[(q3["carga"] == carga) & (q3["versao"].astype(str) == v) & (q3["compilacao"] == comp)]
                d = d.sort_values("threads")
                ax.plot(d["threads"], d["speedup"], marker="o", ms=7, color=COR_COMPILACAO[comp],
                        label=NOME_COMPILACAO[comp], markeredgecolor=SUPERFICIE, markeredgewidth=1.5)
            ax.set_xticks(threads)
            ax.yaxis.set_major_formatter(virgula(1))
            if i == 0:
                ax.set_title(f"Python {v}", loc="center")
            if j == 0:
                ax.set_ylabel(f"{NOME_CARGA[carga]}\nspeedup")
            if i == len(cargas) - 1:
                ax.set_xlabel("threads")
    eixos[0][0].legend(loc="upper left", fontsize=8.5)
    fig.suptitle("G3 · Mais threads = mais rápido? (speedup relativo à compilação padrão com 1 thread)",
                 x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    return _salvar(fig, destino)


def g4_variabilidade(cv: pd.DataFrame, limite: float, destino: Path) -> str:
    """Estabilidade das medições: CV dos valores do pyperf em cada bloco × interpretador × benchmark."""
    interps = [i for i in ["3.13", "3.13t", "3.14", "3.14t", "3.15", "3.15t"] if i in set(cv["interp"])]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    dados = [cv.loc[cv["interp"] == i, "cv"] * 100 for i in interps]
    ax.boxplot(dados, widths=0.45, showfliers=True, patch_artist=True,
               boxprops={"facecolor": "#dcdad3", "edgecolor": TEXTO_2},
               medianprops={"color": TEXTO, "linewidth": 2}, whiskerprops={"color": TEXTO_2},
               capprops={"color": TEXTO_2}, flierprops={"markeredgecolor": TEXTO_2, "markersize": 4})
    ax.axhline(limite * 100, color="#e34948", linewidth=1.5, linestyle="--")
    ax.text(0.6, limite * 100, f"limite de instabilidade ({limite:.0%})", color=TEXTO_2, va="bottom", fontsize=8.5)
    ax.set_xticks(range(1, len(interps) + 1), interps)
    ax.set_ylabel("coeficiente de variação (%)")
    ax.set_title("G4 · As medições foram estáveis?", loc="left")
    ax.grid(axis="x", visible=False)
    return _salvar(fig, destino)
