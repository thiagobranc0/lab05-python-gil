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

**Atualizar de versão (código de uma thread).** Numa função serverless, o custo de execução é proporcional à
duração: o AWS Lambda cobra US$ 0,0000166667 por GB-s (x86, US East · N. Virginia), mais US$ 0,20 por milhão de
requisições ([preços do AWS Lambda](https://aws.amazon.com/lambda/pricing/), acesso em 22/11/2026). Com o speedup
medido no Q1, passar da 3.13 para a 3.14 reduz a duração em 14,0 % (IC 95 %: 9,7 % a 18,5 %), e para a 3.15, em
16,7 % (12,7 % a 20,9 %). Exemplo: uma função de 512 MB que roda 1 s por chamada, 10 milhões de vezes por mês, gasta
cerca de US$ 83,33 de execução na 3.13; na 3.14 gastaria cerca de US$ 71,65, ou US$ 11,68 a menos por mês, sem mudar
código. O custo das requisições (US$ 2,00) não muda. Em capacidade, o mesmo servidor atende cerca de 16 % (3.14) a
20 % (3.15) mais requisições desse tipo.

**Adotar o free-threading.** Com uma thread, tirar a GIL custa 10,5 % (3.14t) a 11,4 % (3.15t) a mais de duração;
no exemplo acima, cerca de US$ 8,75 a mais por mês na 3.14t. Só compensa quando o código usa threads de verdade em
trabalho de CPU: com 4 threads, a 3.14t foi cerca de 2× mais rápida nestes runners. No Lambda gerenciado isso ainda
nem é opção: o runtime Python 3.14 não permite desligar a GIL
([AWS Compute Blog, 18/11/2025](https://aws.amazon.com/blogs/compute/python-3-14-runtime-now-available-in-aws-lambda/),
acesso em 22/11/2026), e o `python3.15` está em prévia pública, fora do SLA
([Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html), acesso em 22/11/2026).

| Decisão | Para que tipo de carga | Efeito medido |
|---|---|---|
| 3.13 → 3.14 ou 3.15 | código Python puro, uma thread | −14,0 % a −16,7 % de duração e de custo de execução |
| padrão → free-threaded, 1 thread | código sem threads | +10,5 % a +11,4 % de duração |
| padrão → free-threaded, 4 threads | CPU em Python, cada thread com os seus dados | cerca de 2× mais rápido |
| padrão → 3.15t, objeto compartilhado | threads lendo o mesmo objeto | sem ganho (0,96×) |

**O que não se pode afirmar.**

- Que uma aplicação real terá esses ganhos: os benchmarks são CPU-bound e em Python puro. Funções serverless costumam
  passar boa parte do tempo esperando rede ou banco de dados, e essa parte nenhuma versão acelera.
- Que o ganho sem GIL é de 2× em qualquer máquina: os runners têm 4 vCPUs (2 núcleos físicos com hyperthreading).
  Com mais núcleos o resultado pode ser outro, e isso não foi medido.
- Que a economia vale para outros provedores ou para Arm: a conta usa só o preço x86 do Lambda numa região, e no
  Lambda a fatia de CPU depende da memória configurada.
- Que a regressão da 3.15t com objeto compartilhado vai continuar: medimos uma versão de patch (3.15.2), e o
  resultado é exploratório.
- Que bibliotecas com extensões em C se comportam igual: elas podem não ter versão para o free-threaded ou religar a
  GIL ao serem importadas.

## 8. Histórico de execuções

{{HISTORICO}}

## 9. Reproduzir

- **Coleta:** aba *Actions* → *benchmark* → *Run workflow* (modo `teste`, `piloto` ou `completo`; nº de blocos).
- **Análise local:** `pip install -r requirements.txt && python build.py`
