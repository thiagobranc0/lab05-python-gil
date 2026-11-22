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

**Interpretação.** Rejeitamos H₀: em código de uma thread, as versões novas são mais rápidas que a 3.13. A 3.14
é 1,163× mais rápida (IC 95 % 1,107 – 1,227; 21 de 22 benchmarks) e a 3.15, 1,201× (IC 1,146 – 1,264; 22 de 22),
com efeito quase máximo (rank-biserial −0,99 e −1,00; p Holm < 0,001). Da 3.14 para a 3.15 o ganho é menor, mas
consistente (p Holm = 0,003; rank-biserial −0,75). O ganho não é uniforme: vai de quase zero (`pidigits`, que passa
o tempo em aritmética de inteiros grandes, em C) a cerca de 50 % (`deepcopy`, `go`); por isso a média geométrica
vem sempre acompanhada da distribuição no G1.

### Q2 · Quanto custa tirar a GIL? (uma thread)

{{Q2}}

**Interpretação.** Rejeitamos H₀ nas três versões: sem GIL, o código de uma thread fica mais lento (p Holm < 0,001;
rank-biserial 0,89 a 0,99). O custo caiu de 33,4 % na 3.13t para 10,5 % na 3.14t e 11,4 % na 3.15t. Os ICs da
3.14t e da 3.15t se sobrepõem, então não dá para dizer que a 3.15t piorou em relação à 3.14t. A queda coincide com a
3.14, versão em que o free-threading passou a ser suportado oficialmente (PEP 779).

### Q3 · Sem GIL, mais threads = mais rápido?

{{Q3}}

**Interpretação.** Rejeitamos H₀ nas três cargas em Python: o efeito de ter mais threads depende da compilação
(interação compilação × threads com p Holm < 0,001 e η² parcial de 0,45 a 0,98). Com GIL, 4 threads não ajudam
(0,97× a 0,99×); sem GIL, dão cerca de 2× na CPU em Python puro e no JSON com cópia por thread, nestes runners de
2 núcleos físicos com hyperthreading. O controle `hashlib`, que já libera a GIL, escala 3,7× nas duas compilações e
não tem interação (p Holm = 0,710): o instrumento mede o efeito da GIL, e não outra diferença entre as compilações.
Exploratório: com objeto compartilhado, a 3.13t e a 3.14t escalam (1,83× e 1,90× com 4 threads), mas a 3.15t não
(0,96×). É um achado a confirmar, não uma hipótese testada.

**Pressupostos da ANOVA.** Os resíduos têm caudas pesadas e variância desigual entre as células (curtose de 17 a 34
nas cargas `cpu_puro`, `json` e `hash_controle`; teste de Levene com p < 0,05 nas quatro cargas), e as 10 repetições
de um mesmo bloco não são independentes entre si. Por isso refizemos o modelo planejado sobre a mediana de cada
célula (bloco × versão × compilação × threads; n = 180 por carga): as decisões sobre a interação compilação × threads
não mudam (p < 0,001 nas três cargas em Python; p = 0,93 no controle). Na interação tripla exploratória, só o
`json_compartilhado` continua forte (η² parcial 0,96); no `cpu_puro` ela deixa de ser significativa (p = 0,11) e no
`json` fica fraca (p = 0,01). Ou seja, a única diferença entre versões que resiste à checagem é a regressão da
3.15t com objeto compartilhado.

### Q4 · Memória

{{Q4}}

**Interpretação.** Sem GIL, o pico de memória do processo é 4 % a 6 % maior (cerca de 1 a 2 MiB sobre ~36 MiB) e
cresce um pouco com o número de threads. É uma medida só descritiva, em processos pequenos: não dá para projetar a
diferença para aplicações grandes.

### Testes de hipótese

{{TESTES}}

### Estabilidade das medições

{{ESTABILIDADE}}

**Interpretação.** A variação entre repetições é pequena (CV mediano de 1,6 % com uma thread e de 1,0 % com threads,
segundo a validação automática), muito menor que os efeitos medidos, de 10 % ou mais. Os runners caíram em 3 modelos
de CPU, mas cada runner mede os 6 interpretadores: essa diferença fica no fator bloco e não enviesa as comparações.

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
