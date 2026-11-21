"""Gera o README.md (o documento/dashboard do estudo) a partir de docs/README.base.md e dos dados.

Uso: python build.py [--execucao <id>]
Sem --execucao, usa a execução principal (bench/config.py: EXECUCAO_PRINCIPAL); se ela não existir, a última
execução válida (completo > piloto > teste). Coletas completas posteriores entram na seção "Replicação".
O texto fixo fica em docs/README.base.md; os trechos {{...}} são preenchidos aqui com tabelas e gráficos.
Roda automaticamente no workflow depois de cada coleta validada.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "bench"))
import analise  # noqa: E402
import config  # noqa: E402
import graficos  # noqa: E402

IMAGENS = RAIZ / "images"
AGUARDANDO = "_Aguardando a primeira execução válida do workflow._"


def num(x, casas=2, sufixo="") -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".") + sufixo


def pval(p) -> str:
    if p is None or np.isnan(p):
        return "–"
    return "< 0,001" if p < 0.001 else num(p, 3)


def tabela(linhas: list[list], cabecalho: list[str]) -> str:
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    out += ["| " + " | ".join(map(str, l)) + " |" for l in linhas]
    return "\n".join(out)


def sec_execucao(d: analise.Dados) -> str:
    amb = d.amb
    cpus = amb["cpu_modelo"].value_counts()
    versoes = [f"{i} = {amb[f'versao_{i}'].iloc[0]}" for i in config.INTERPRETADORES if f"versao_{i}" in amb]
    status = "✅ OK" if d.validacao["status"] == "ok" else "❌ FALHA"
    linhas = [
        ["Execução", f"`{d.execucao}`"],
        ["Modo", f"`{d.modo}`"],
        ["Blocos (runners)", f"{len(amb)}"],
        ["CPUs", "; ".join(f"{m} ({n} bloco{'s' if n > 1 else ''})" for m, n in cpus.items())],
        ["vCPUs por runner", ", ".join(map(str, sorted(amb["n_cpus"].unique())))],
        ["Núcleos físicos × threads por núcleo",
         ", ".join(sorted({f"{int(n * s)} × {int(t)}" for n, s, t in
                           amb[["nucleos_por_soquete", "soquetes", "threads_por_nucleo"]].dropna().itertuples(index=False)}))
         if "threads_por_nucleo" in amb else "não registrado"],
        ["Interpretadores", "; ".join(versoes)],
        ["Início (UTC)", str(amb["inicio_utc"].min())],
        ["Duração dos blocos", f"{num(amb['duracao_min'].min(), 0)}–{num(amb['duracao_min'].max(), 0)} min"],
        ["Validação automática", f"{status} · [relatório](data/processed/{d.execucao}/VALIDACAO.md) · "
                                 f"{len(d.validacao['avisos'])} aviso(s)"],
    ]
    return tabela(linhas, ["", ""])


def sec_q1(r: analise.Resultado) -> str:
    if r.q1.empty:
        return AGUARDANDO
    img = graficos.g1_speedup_versoes(r.q1, IMAGENS / "g1_speedup_versoes.png")
    linhas = [[x["comparacao"], num(x["speedup_gmean"], 3) + "×", f"{num(x['ic_lo'], 3)} – {num(x['ic_hi'], 3)}",
               f"{x['mais_rapidos']} de {x['n']}"] for _, x in r.q1_resumo.iterrows()]
    return (f"![G1](images/{img})\n\n"
            + tabela(linhas, ["Comparação", "Speedup (média geométrica)", "IC 95%", "Benchmarks mais rápidos"])
            + "\n\n<details><summary>Speedup por benchmark</summary>\n\n"
            + tabela([[b] + [num(v, 3) for v in row] for b, row in r.q1.iterrows()],
                     ["Benchmark"] + [f"{v} ÷ 3.13" for v in r.q1.columns])
            + "\n\n</details>")


def sec_q2(r: analise.Resultado) -> str:
    if r.q2.empty:
        return AGUARDANDO
    img = graficos.g2_custo_free_threaded(r.q2, r.q2_resumo, IMAGENS / "g2_custo_free_threaded.png")
    linhas = [[f"{x['versao']}t ÷ {x['versao']}", num(x["razao_gmean"], 3) + "×",
               f"{num(x['ic_lo'], 3)} – {num(x['ic_hi'], 3)}", num((x["razao_gmean"] - 1) * 100, 1, " %"),
               f"{x['mais_lentos']} de {x['n']}"] for _, x in r.q2_resumo.iterrows()]
    return (f"![G2](images/{img})\n\n"
            + tabela(linhas, ["Comparação", "Razão de tempo (média geométrica)", "IC 95%", "Custo",
                              "Benchmarks mais lentos sem GIL"]))


def sec_q3(r: analise.Resultado) -> str:
    if r.q3.empty:
        return AGUARDANDO
    img = graficos.g3_escalonamento(r.q3, IMAGENS / "g3_escalonamento.png")
    tmax = r.q3["threads"].max()
    d = r.q3[r.q3["threads"] == tmax].pivot_table(index=["carga", "versao"], columns="compilacao", values="speedup")
    linhas = [[graficos.NOME_CARGA.get(c, c), v, num(row.get("padrao"), 2) + "×", num(row.get("free-threaded"), 2) + "×"]
              for (c, v), row in d.iterrows()]
    anova = [[graficos.NOME_CARGA.get(x["carga"], x["carga"]), x["efeito"], num(x["F"], 1),
              pval(x["p"]), num(x["eta2_parcial"], 3)] for _, x in r.q3_anova.iterrows()]
    return (f"![G3](images/{img})\n\n"
            + f"Speedup com {tmax} threads, relativo à compilação padrão com 1 thread da mesma versão:\n\n"
            + tabela(linhas, ["Carga", "Versão", "Padrão (com GIL)", "Free-threaded (sem GIL)"])
            + "\n\nANOVA fatorial sobre log(tempo), uma por carga (modelo planejado: compilação × threads + versão + bloco). "
            + "A última linha de cada carga vem de um segundo modelo, **exploratório**, com a interação tripla "
            + "compilação × threads × versão: ela testa se o ganho com threads sem GIL muda entre as versões.\n\n"
            + tabela(anova, ["Carga", "Efeito", "F", "p", "η² parcial"]))


def sec_q4(r: analise.Resultado) -> str:
    if r.q4.empty:
        return AGUARDANDO
    linhas = [[graficos.NOME_CARGA.get(x["carga"], x["carga"]), x["threads"], num(x["rss_padrao_mb"], 1),
               num(x["rss_ft_mb"], 1), num(x["razao"], 2) + "×"] for _, x in r.q4.iterrows()]
    return tabela(linhas, ["Carga", "Threads", "Pico de RSS padrão (MiB)", "Pico de RSS sem GIL (MiB)",
                           "Razão (média geométrica)"])


def sec_testes(r: analise.Resultado) -> str:
    if r.testes.empty:
        return AGUARDANDO
    linhas = []
    for _, x in r.testes.iterrows():
        efeito = (f"rank-biserial = {num(x['rb'], 2)}" if not np.isnan(x.get("rb", np.nan))
                  else f"η²p = {num(x.get('eta2_parcial'), 3)}")
        estat = "W" if x["questao"] in ("Q1", "Q2") else "F"
        linhas.append([x["questao"], x["teste"], int(x["n"]), f"{estat} = {num(x['W'], 1)}", pval(x["p"]),
                       pval(x["p_holm"]), efeito])
    return tabela(linhas, ["Q", "Teste", "n", "Estatística", "p", "p (Holm)", "Tamanho do efeito"])


def sec_estabilidade(r: analise.Resultado) -> str:
    if r.cv_st.empty:
        return AGUARDANDO
    img = graficos.g4_variabilidade(r.cv_st, config.LIMITE_CV, IMAGENS / "g4_variabilidade.png")
    return f"![G4](images/{img})"


LIMIAR_Q3 = 1.2  # Q3: sem GIL "ganha" se o speedup com tmax threads for ≥ 1,2× o da compilação padrão


def _lado_ic(lo: float, hi: float) -> str:
    return "acima de 1" if lo > 1 else ("abaixo de 1" if hi < 1 else "inclui 1")


def _veredito_q3(ft: float, padrao: float) -> str:
    razao = ft / padrao
    return "sem GIL ganha" if razao >= LIMIAR_Q3 else ("com GIL ganha" if razao <= 1 / LIMIAR_Q3 else "empate")


def sec_replicacao(principal: str | None, r: analise.Resultado | None) -> str:
    """Compara as conclusões da execução principal com as de cada replicação (#13)."""
    reps = analise.replicacoes(principal)
    if r is None or not reps:
        return "_Aguardando a replicação (#13): uma coleta completa em outro horário, comparada aqui com a principal._"
    outras = [(e, analise.analisar(analise.carregar(e))) for e in reps]
    cab_rep = [f"Replicação {i}" for i in range(1, len(outras) + 1)]
    sim = lambda vs: "sem dados" if "–" in vs else ("✅ sim" if len(set(vs)) == 1 else "❌ não")

    q1 = []
    for _, x in r.q1_resumo.iterrows():
        vals, lados = [x], [_lado_ic(x["ic_lo"], x["ic_hi"])]
        for _, ro in outras:
            y = ro.q1_resumo.set_index("comparacao").loc[x["comparacao"]]
            vals.append(y); lados.append(_lado_ic(y["ic_lo"], y["ic_hi"]))
        q1.append([x["comparacao"]] + [num(v["speedup_gmean"], 3) + "×" for v in vals] + [lados[0], sim(lados)])

    q2 = []
    for _, x in r.q2_resumo.iterrows():
        vals, lados = [x], [_lado_ic(x["ic_lo"], x["ic_hi"])]
        for _, ro in outras:
            y = ro.q2_resumo.set_index("versao").loc[x["versao"]]
            vals.append(y); lados.append(_lado_ic(y["ic_lo"], y["ic_hi"]))
        q2.append([f"{x['versao']}t ÷ {x['versao']}"] + [num((v["razao_gmean"] - 1) * 100, 1, " %") for v in vals]
                  + [lados[0], sim(lados)])

    def q3_tab(res: analise.Resultado) -> pd.DataFrame:
        tmax = res.q3["threads"].max()
        return res.q3[res.q3["threads"] == tmax].pivot_table(index=["carga", "versao"], columns="compilacao",
                                                              values="speedup")
    base = q3_tab(r)
    tabs = [q3_tab(ro) for _, ro in outras]
    q3 = []
    for (c, v), x in base.iterrows():
        vals = [x] + [t.loc[(c, v)] if (c, v) in t.index else None for t in tabs]
        veredits = [_veredito_q3(y["free-threaded"], y["padrao"]) if y is not None else "–" for y in vals]
        q3.append([graficos.NOME_CARGA.get(c, c), v]
                  + [num(y["free-threaded"], 2) + "×" if y is not None else "–" for y in vals]
                  + [veredits[0], sim(veredits)])

    lista = "; ".join(f"replicação {i} = `{e}`" for i, (e, _) in enumerate(outras, 1))
    return (f"Principal = `{principal}`; {lista}. A replicação repete o mesmo desenho em outro horário (outros "
            "runners). **A conclusão se mantém** quando a decisão é a mesma na principal e em cada replicação: no Q1 e no Q2, o lado do "
            f"IC 95 % em relação a 1; no Q3, se sem GIL o speedup com 4 threads é ≥ {num(LIMIAR_Q3, 1)}× o da "
            "compilação padrão (\"sem GIL ganha\"), ≤ o inverso (\"com GIL ganha\") ou fica entre os dois (\"empate\").\n\n"
            + "**Q1 · speedup sobre a 3.13**\n\n"
            + tabela(q1, ["Comparação", "Principal"] + cab_rep + ["IC 95 % (principal)", "Conclusão mantida?"])
            + "\n\n**Q2 · custo sem GIL (uma thread)**\n\n"
            + tabela(q2, ["Comparação", "Principal"] + cab_rep + ["IC 95 % (principal)", "Conclusão mantida?"])
            + "\n\n**Q3 · speedup sem GIL com 4 threads**\n\n"
            + tabela(q3, ["Carga", "Versão", "Principal"] + cab_rep + ["Decisão (principal)", "Conclusão mantida?"]))


def sec_historico() -> str:
    indice = RAIZ / "data" / "execucoes.csv"
    if not indice.exists():
        return "_Nenhuma execução ainda._"
    ex = pd.read_csv(indice).sort_values("validado_utc", ascending=False)
    linhas = [[f"`{x['execucao']}`", x["modo"], x["blocos"], "✅" if x["status"] == "ok" else "❌",
               x["avisos"], f"[relatório](data/processed/{x['execucao']}/VALIDACAO.md)"] for _, x in ex.iterrows()]
    return tabela(linhas, ["Execução", "Modo", "Blocos", "Validação", "Avisos", ""])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows não é UTF-8
    p = argparse.ArgumentParser()
    p.add_argument("--execucao")
    a = p.parse_args()

    IMAGENS.mkdir(exist_ok=True)
    execucao = a.execucao or analise.escolher_execucao()
    secoes = {k: AGUARDANDO for k in ("EXECUCAO", "Q1", "Q2", "Q3", "Q4", "TESTES", "ESTABILIDADE")}
    r = None
    if execucao:
        d = analise.carregar(execucao)
        r = analise.analisar(d)
        secoes.update(EXECUCAO=sec_execucao(d), Q1=sec_q1(r), Q2=sec_q2(r), Q3=sec_q3(r), Q4=sec_q4(r),
                      TESTES=sec_testes(r), ESTABILIDADE=sec_estabilidade(r))
        if d.modo != "completo":
            secoes["EXECUCAO"] = (f"> ⚠️ Resultados da execução **{d.modo}**: servem para testar o pipeline e "
                                  "calibrar o desenho, não como resultado do estudo.\n\n" + secoes["EXECUCAO"])
    secoes["REPLICACAO"] = sec_replicacao(execucao, r)
    secoes["HISTORICO"] = sec_historico()

    texto = (RAIZ / "docs" / "README.base.md").read_text(encoding="utf-8")
    for chave, valor in secoes.items():
        texto = texto.replace("{{" + chave + "}}", valor)
    (RAIZ / "README.md").write_text(texto, encoding="utf-8")
    print(f"README.md gerado ({execucao or 'sem dados'})")


if __name__ == "__main__":
    main()
