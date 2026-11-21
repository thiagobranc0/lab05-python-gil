# Desenho experimental

Toda a configuração está em [`config.py`](config.py). Mudou o desenho? Mude lá e registre aqui, com a data e o motivo.

## Objeto, tratamentos e fatores

| Fator | Níveis | Tipo |
|---|---|---|
| Versão do CPython | 3.13, 3.14, 3.15 | ordinal |
| Compilação | padrão (com GIL) · free-threaded (sem GIL, sufixo `t`) | nominal |
| Threads (só nas cargas com threads) | 1, 2, 4 | razão, tratada como fator |
| Carga | 20 benchmarks do pyperformance (uma thread) · 3 cargas próprias (várias threads) | nominal |
| **Bloco** | cada runner do GitHub Actions | fator de bloqueio |

Os 6 interpretadores (3 versões × 2 compilações) são instalados com `uv python install` (builds do projeto
python-build-standalone, os mesmos em qualquer máquina Linux x86-64). A **versão do uv é fixada**
(`UV_VERSAO` = 0.13.9), porque é ela que define qual build existe para cada "3.x": com ela, todos os runners
instalam **3.13.18, 3.14.10 e 3.15.2** (versões finais, conferidas em 20/11/2026). A validação recusa
versões diferentes dessas e versões alfa/beta/rc no modo completo.

## Variáveis dependentes

| Métrica | Como é medida | Escala |
|---|---|---|
| Tempo de um benchmark (s) | pyperf: vários processos, aquecimento descartado; usamos a mediana dos valores no bloco | razão |
| Tempo de uma carga com threads (s) | `time.perf_counter` entre a largada (barreira) e o fim de todas as threads | razão |
| Speedup | razão de tempos (derivada) | razão |
| Pico de memória (MiB) | `resource.getrusage(...).ru_maxrss` do processo | razão |

## Cargas com várias threads ([`mt_workloads.py`](mt_workloads.py))

Escala forte: o **trabalho total é fixo** e é dividido igualmente entre as threads.

| Carga | O que faz | O que se espera |
|---|---|---|
| `cpu_puro` | conta primos por divisão, em Python puro | com GIL não escala; sem GIL deveria escalar |
| `json` | `json.dumps` + `json.loads` de um documento médio, **cada thread com a sua cópia** | idem |
| `json_compartilhado` | o mesmo, mas **todas as threads sobre o mesmo objeto** | mede o custo de compartilhar objetos sem a GIL (cada objeto tem a sua trava) |
| `hash_controle` | SHA-256 de buffers de 4 MiB | **controle**: o `hashlib` já libera a GIL, então escala nas duas compilações |

Cada execução tem um aquecimento não medido (2 % do trabalho) e devolve um `checksum`. O mesmo trabalho
tem de dar o mesmo checksum em todo interpretador: a validação confere isso.

## Blocos, ordem e repetições

- **Bloco = runner.** Cada runner mede **todos** os 6 interpretadores, então toda comparação entre
  interpretadores é feita dentro da mesma máquina (pareada). Runners diferentes podem ter CPUs diferentes;
  isso vira variação **entre** blocos, não viés **dentro** do bloco.
- **Ordem sorteada** dentro do bloco, com semente `SEMENTE_BASE + nº do bloco` (reprodutível):
  - uma thread: a ordem dos 6 interpretadores no pyperformance;
  - várias threads: todas as combinações interpretador × carga × threads × repetição embaralhadas juntas.
- **Repetições:** o próprio pyperf repete cada benchmark em vários processos. Nas cargas com threads,
  `mt_reps` repetições por combinação.

| Modo | pyperformance | Repetições (threads) | Para quê |
|---|---|---|---|
| `teste` | 3 benchmarks, 1 valor | 1 (trabalho reduzido) | conferir que o pipeline roda |
| `piloto` | 20 benchmarks, `--fast` | 3 | calibrar e achar benchmarks que não rodam |
| `completo` | 20 benchmarks, padrão | 10 | dataset do estudo |

## Tamanho da coleta completa (decidido com o piloto de 20/11)

O piloto (2 blocos, `20261120-1758_piloto_44788346764`) mediu variação pequena: coeficiente de variação
mediano de 1,5 % entre os valores do pyperf e de 0,6 % entre as repetições das cargas com threads. Os efeitos
observados são de 10 % ou mais. Com esse ruído, poucas repetições já bastam para detectar esses efeitos, então o
nº de blocos **não** é escolhido por poder estatístico, e sim por **generalização entre máquinas**: mais
runners = mais chance de pegar CPUs e vizinhos diferentes. Escolha: **10 blocos**, modo `completo`
(pyperf no modo padrão, 10 repetições por combinação nas cargas com threads). Duração estimada: ~1 h por
bloco, em paralelo.

## Pipeline automático ([`.github/workflows/benchmark.yml`](../.github/workflows/benchmark.yml))

1. `preparar`: define a lista de blocos e o identificador da execução.
2. `bloco` (N runners em paralelo): instala os interpretadores, roda [`run_block.py`](run_block.py), publica o artifact.
3. `consolidar`: junta os blocos ([`src/consolidar.py`](../src/consolidar.py)), **valida**
   ([`src/validar.py`](../src/validar.py)), gera o README ([`build.py`](../build.py)), grava tudo em `data/`
   e, no modo completo, cria a tag `dataset-<execução>`. Se a validação falhar, abre uma issue com o relatório.

Um segundo workflow, [`readme.yml`](../.github/workflows/readme.yml), regenera o README sem coletar de novo
sempre que muda o texto (`docs/README.base.md`) ou a análise; usa a última execução válida em `data/`.

## Registro de mudanças

| Data | Mudança | Motivo |
|---|---|---|
| 20/11/2026 | Desenho inicial | – |
| 20/11/2026 | `json` passa a usar uma cópia por thread; nova carga `json_compartilhado`; topologia da CPU registrada | o piloto mostrou a 3.15t sem ganho nenhum com threads no `json`; teste local confirmou que a causa é a disputa pelo objeto compartilhado (3.15.2t: 0,63 → 0,45 → 0,71 s com 1/2/4 threads; com cópia por thread: 0,62 → 0,32 → 0,17 s; a 3.14.10t escala nos dois casos). A carga original misturava vazão do JSON com disputa pelo objeto; agora são duas cargas. A topologia explica o escalonamento abaixo do ideal de 2 para 4 threads |
| 20/11/2026 | uv fixado em 0.13.9 | o teste local com um uv antigo instalou a 3.15.0a5 (alfa); fixar o uv torna as versões reprodutíveis |
| 20/11/2026 | Coleta completa `20261120-2001_completo_44807518024`: 10 blocos, validação ok | – |
| 20/11/2026 | ANOVA **exploratória** com a interação tripla compilação × threads × versão, ao lado do modelo planejado (que fica igual) | a coleta completa confirmou que, no `json_compartilhado`, só a 3.15t não escala; o modelo planejado trata a versão só como efeito principal e não consegue mostrar isso. Como foi decidida **depois** de ver os dados, é apresentada como exploratória, não como confirmatória |
| 20/11/2026 | Execução principal fixada em `bench/config.py` (`EXECUCAO_PRINCIPAL`); coletas completas posteriores entram no README como **replicação**, comparadas com a principal | sem isso, a replicação (#13) substituiria a análise principal no README. A replicação existe para mostrar se as conclusões se repetem em outro horário, não para trocar os números. Regra de "conclusão mantida" definida **antes** da replicação: mesmo lado do IC 95 % em relação a 1 (Q1, Q2); mesma decisão com limiar de 1,2× (Q3) |
