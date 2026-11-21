<!-- ESTE É O MODELO DO README. Edite aqui, não no README.md (ele é gerado por `python build.py`).
     Os trechos entre chaves duplas são preenchidos automaticamente com tabelas e gráficos. -->

# CPython com e sem GIL: as versões novas cumprem o que prometem?

Laboratório 05 · Experimento em software real · Laboratório de Experimentação de Software · Engenharia de Software · PUC Minas · 2026/2

- **Repositório:** https://github.com/thiagobranc0/lab05-python-gil
- **GitHub Projects:** https://github.com/users/thiagobranc0/projects/2
- **Como o experimento roda:** [`bench/DESENHO.md`](bench/DESENHO.md) · **Guia de defesa:** [`docs/DEFESA.md`](docs/DEFESA.md)

> Este README é gerado por código a cada coleta validada (`python build.py`). A coleta, a validação e a
> geração rodam sozinhas no GitHub Actions ([workflow](.github/workflows/benchmark.yml)); não há etapa manual.

## 1. O software

O **CPython** é a implementação de referência da linguagem Python, mantida pela Python Software Foundation.

| Critério | Evidência | Fonte |
|---|---|---|
| Real | _a preencher (#2)_ | |
| Em operação | Versões mantidas em 20/11/2026: 3.15 e 3.14 (bugfix), 3.13 (security) | [devguide.python.org/versions](https://devguide.python.org/versions/) (acesso em 20/11/2026) |
| Alto impacto | _a preencher (#2)_ | |

## 2. Pergunta, GQM e hipóteses

**Pergunta:** As versões recentes do CPython e a compilação sem GIL (free-threaded) entregam os ganhos de
desempenho anunciados, e a que custo para o código de uma thread só?

| Questão | Métrica | H₀ | H₁ |
|---|---|---|---|
| Q1 · Cada versão nova é mais rápida em código de uma thread? | tempo por benchmark (pyperformance); speedup | o tempo não muda entre versões | o tempo muda entre versões |
| Q2 · Quanto custa tirar a GIL em código de uma thread? | razão de tempo free-threaded ÷ padrão | o tempo é igual com e sem GIL | o tempo é diferente sem GIL |
| Q3 · Sem GIL, mais threads deixam o código mais rápido? | speedup com 1, 2 e 4 threads | não há interação compilação × threads | há interação compilação × threads |
| Q4 · Quanto de memória a mais o free-threaded usa? | pico de RSS | (descritiva) | (descritiva) |

_Objetivo GQM no template de Basili, entidades, atributos e escalas: a preencher (#3)._

## 3. Desenho em uma frase

Experimento controlado, fatorial e em blocos: **6 interpretadores** (3.13, 3.14 e 3.15, cada um com e sem
GIL) rodam os mesmos benchmarks em cada **runner do GitHub Actions** (um bloco), em ordem sorteada;
vários runners em paralelo dão as réplicas. Detalhes em [`bench/DESENHO.md`](bench/DESENHO.md).

## 4. A execução analisada

{{EXECUCAO}}

## 5. Resultados

### Q1 · Cada versão nova é mais rápida? (uma thread)

{{Q1}}

### Q2 · Quanto custa tirar a GIL? (uma thread)

{{Q2}}

### Q3 · Sem GIL, mais threads = mais rápido?

{{Q3}}

### Q4 · Memória

{{Q4}}

### Testes de hipótese

{{TESTES}}

### Estabilidade das medições

{{ESTABILIDADE}}

### Replicação

{{REPLICACAO}}

## 6. Ameaças à validade

_A preencher (#17)._

## 7. Impacto

_A preencher (#18)._

## 8. Histórico de execuções

{{HISTORICO}}

## 9. Reproduzir

- **Coleta:** aba *Actions* → *benchmark* → *Run workflow* (modo `teste`, `piloto` ou `completo`; nº de blocos).
- **Análise local:** `pip install -r requirements.txt && python build.py`
