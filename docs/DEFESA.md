# Guia de defesa

Para os três integrantes: o que cada parte faz, por que foi feita assim e as perguntas prováveis do professor.
Este guia acompanha o projeto e será fechado com os resultados reais (seções marcadas com ⏳).

## 1. O estudo em 30 segundos

O Python é uma das linguagens mais usadas do mundo, e o CPython é o interpretador que quase todo mundo roda.
Desde a 3.11, cada versão anuncia ganhos de desempenho; desde a 3.13, existe uma compilação **sem GIL**
(free-threaded), que promete paralelismo de verdade com threads, ao custo de deixar o código de uma thread
mais lento. Nós **medimos** essas promessas num experimento controlado: 6 interpretadores (3.13, 3.14 e 3.15,
com e sem GIL), os mesmos benchmarks, na mesma máquina, em ordem sorteada, repetido em vários runners.

## 2. Conceitos que precisam estar na ponta da língua

| Conceito | Explicação curta |
|---|---|
| **GIL** | *Global Interpreter Lock*: uma trava que deixa só uma thread executar bytecode Python por vez. Simplifica o interpretador, mas impede paralelismo em código CPU-bound. |
| **Free-threaded** | Compilação do CPython sem a GIL (PEP 703; suporte oficial pela PEP 779 a partir da 3.14). Instalada com o sufixo `t` (ex.: `3.14t`). |
| **CPU-bound × I/O-bound** | CPU-bound passa o tempo calculando (a GIL atrapalha); I/O-bound passa esperando disco/rede (a GIL é liberada na espera). |
| **pyperformance / pyperf** | A suíte oficial de benchmarks do CPython e a biblioteca que a executa: roda cada benchmark em vários processos, descarta o aquecimento e guarda todos os valores. |
| **Speedup** | tempo de referência ÷ tempo novo. 1,10 = 10 % mais rápido. |
| **Média geométrica** | O jeito certo de fazer média de razões (speedups). A média aritmética de razões é enviesada. |
| **Escala forte** | Trabalho total fixo dividido entre as threads. Escala perfeita: 2 threads = metade do tempo. |

## 3. Por que este desenho (perguntas prováveis)

**Por que isso é um software "real, em operação e de alto impacto"?**
⏳ Números do #2 (Stack Overflow Survey, TIOBE, PyPI, nuvem). Versões mantidas conferidas no devguide em 20/11/2026.

**Não é "minerar repositório do GitHub", que o enunciado proíbe?**
Não. O objeto é o **interpretador em funcionamento**, executando programas; o GitHub Actions é só a máquina
onde o experimento roda. O enunciado aceita explicitamente "rodar no ambiente do grupo a mesma versão que roda em produção".

**Por que blocos? Os runners não são todos iguais?**
Não são: o GitHub sorteia máquinas com CPUs diferentes e vizinhos barulhentos. Por isso **cada runner mede
todos os 6 interpretadores**: a comparação 3.14 × 3.13 é sempre feita na mesma máquina. A diferença entre
máquinas vira variação entre blocos (o fator `bloco` na ANOVA), não viés.

**Por que sortear a ordem?**
Se o 3.13 sempre rodasse primeiro, qualquer efeito do tempo (aquecimento da máquina, vizinho que chegou
depois) se confundiria com o efeito da versão. Sorteando com semente fixa, o efeito da ordem se espalha
entre os tratamentos e o experimento continua reprodutível.

**Por que a carga `hash_controle`?**
É o grupo de controle. O `hashlib` já libera a GIL, então com ou sem GIL ela deveria escalar igual. Se o
free-threaded "ganhasse" nela também, desconfiaríamos do instrumento, não da GIL.

**Por que só benchmarks em Python puro?**
Bibliotecas com extensões em C podem não ter versão para o free-threaded ou religar a GIL ao serem
importadas. Isso mudaria o tratamento sem a gente perceber. A validação confere, em cada execução, se a
GIL estava no estado certo.

**Como vocês garantem que os dados estão certos se ninguém conferiu à mão?**
A validação é código (`src/validar.py`) e roda em toda execução: confere se todos os blocos, interpretadores
e combinações estão presentes, se a GIL estava ligada/desligada como deveria, se o mesmo trabalho deu o
mesmo checksum em todos os interpretadores, se há tempos impossíveis e se a variação entre repetições passou
do limite. Se algo falha, o workflow falha e abre uma issue com o relatório. Validação automática é mais
confiável que olhar planilha: é a mesma regra toda vez, e está versionada.

**Por que Wilcoxon e não teste t?**
Os mesmos benchmarks são medidos em todos os interpretadores (pareado), e as diferenças de log(tempo) entre
benchmarks não têm por que ser normais. O Wilcoxon pareado não exige normalidade. Escolha discutida no Lab04.

**Por que ANOVA no Q3?**
A pergunta do Q3 é sobre **interação**: o efeito de ter mais threads depende da compilação? Interação é
exatamente o que um fatorial com ANOVA testa. Usamos log(tempo) porque o efeito de threads é multiplicativo.

**Por que correção de Holm?**
Fazemos vários testes (Q1, Q2, Q3). Sem correção, a chance de algum falso positivo cresce com o número de
testes. Holm controla o erro da família inteira e é menos conservador que Bonferroni.

**Qual a força da evidência?**
Experimento controlado (o grupo manipula o tratamento e sorteia a ordem), em laboratório, transversal.
É evidência forte para "nestas máquinas e nestas cargas"; a generalização para servidores reais e
aplicações reais é limitada (validade externa, seção 5).

**Vocês mudaram o desenho depois do piloto. Isso não é ajustar o experimento ao resultado?**
O piloto existe justamente para isso, e a mudança foi feita **antes** da coleta completa. O piloto mostrou
que a carga `json` media duas coisas ao mesmo tempo: a vazão do JSON e a disputa de várias threads pelo
mesmo objeto. Separamos em duas cargas (`json`, com uma cópia por thread, e `json_compartilhado`) e
registramos o motivo, com os números do teste local, em `bench/DESENHO.md`. Nada foi removido: a situação
que "deu errado" virou uma carga própria e continua medida.

**E a ANOVA com interação tripla?**
Essa, sim, foi decidida **depois** de ver a coleta completa, e por isso a chamamos de **exploratória**. O
modelo planejado (compilação × threads + versão + bloco) continua lá, sem mudança. O modelo planejado trata a
versão só como efeito principal, então não consegue dizer "o ganho com threads sem GIL é diferente na 3.15".
A ANOVA exploratória acrescenta esse termo. Apresentamos o resultado como um achado a confirmar, não como
hipótese testada. Saber distinguir confirmatório de exploratório é ponto forte na defesa, não fraqueza.

**Como vocês sabem que o resultado não foi sorte daquele horário ou daquelas máquinas?**
Repetimos a coleta completa em outro horário (replicação, #13), com o mesmo desenho. O README continua
analisando a coleta principal e mostra, na seção "Replicação", os números das duas lado a lado com
"conclusão mantida?" em cada linha. A regra do que conta como "mantida" foi escrita **antes** da
replicação rodar (`bench/DESENHO.md`), para não ser ajustada ao resultado.

## 4. Resultados e como interpretá-los

Execução analisada: `20261120-2001_completo_44807518024` (10 blocos, validação ok, tag
`dataset-20261120-2001_completo_44807518024`). Números do README gerado.

**A coleta é confiável?** 0 erros na validação; os 6 interpretadores nas versões finais esperadas; 7200 de
7200 execuções com threads válidas; variação mediana entre repetições de 1,6 % (uma thread) e 1,0 % (com
threads). Os efeitos medidos são de 10 % ou mais, ou seja, muito maiores que o ruído. Os runners caíram em
3 modelos de CPU AMD EPYC (7763, 9V74, 9V45): é o fator bloco que absorve essa diferença.

**Q1 · As versões novas são mais rápidas? (G1)** Sim.
- 3.14 × 3.13: **1,163×** (16,3 % mais rápida; IC 95 % 1,107 – 1,227); 21 de 22 benchmarks mais rápidos.
- 3.15 × 3.13: **1,201×** (IC 95 % 1,146 – 1,264); 22 de 22.
- 3.15 × 3.14: diferença menor (cerca de 3 %), mas consistente (Wilcoxon, p Holm = 0,002, rank-biserial −0,75).
- Como ler o G1: cada ponto é um benchmark; à direita de 1 é mais rápido. O ganho **não é uniforme**:
  `deepcopy` e `go` ganham ~50 %, `pidigits` (que passa o tempo em aritmética de inteiros grandes, em C)
  quase não muda. Por isso a média geométrica sozinha é enganosa (armadilha de Goodhart, #3): é preciso
  mostrar a distribuição.

**Q2 · Quanto custa tirar a GIL? (G2)** Custo caiu muito da 3.13 para a 3.14.
- 3.13t: **33,4 %** mais lenta que a 3.13 com uma thread. 3.14t: **10,5 %**. 3.15t: **11,4 %**.
- Todos significativos (p < 0,001 com Holm), mas o que importa é o tamanho: a 3.14 é a versão em que o
  free-threading passou a ser suportado oficialmente (PEP 779), e o custo de 33 % → ~10 % é coerente com isso.
- Na 3.14t, 3 dos 22 benchmarks **não** ficaram mais lentos sem GIL; o custo depende do tipo de código.

**Q3 · Sem GIL, mais threads = mais rápido? (G3)** Sim, com limites.
- Com GIL, mais threads **não ajudam** em código Python: 0,97× a 0,99× com 4 threads (as threads se revezam).
- Sem GIL: **cerca de 2×** com 4 threads na CPU em Python puro e no JSON com cópia por thread, nas três versões.
  A interação compilação × threads é enorme (η² parcial 0,96 a 0,98): o efeito de threads depende da GIL,
  que é exatamente a hipótese.
- **Controle (`hashlib`):** escala 3,7× com e sem GIL, e a interação **não** é significativa (p = 0,355; η²p
  0,001). É o resultado que valida o instrumento: onde a GIL não importa, as duas compilações empatam.
- **Achado principal: regressão da 3.15t com objeto compartilhado.** Quando as threads leem o **mesmo**
  objeto, a 3.13t (1,83×) e a 3.14t (1,90×) escalam, mas a 3.15t não ganha nada (0,96× com 4 threads). Na
  ANOVA exploratória, a interação tripla é forte só nessa carga (η²p 0,848, contra ~0,02 nas outras e 0
  no controle). Hipótese: sem GIL, cada objeto tem a sua própria trava; na 3.15, serializar um objeto
  passou a segurar essa trava por mais tempo, e as threads ficam na fila. **Não sabemos a mudança
  exata no código do CPython**; o que medimos é o efeito. É o candidato natural para o "anunciado × medido" (#15).
- **Por que ~2× e não 4×?** Os runners têm **2 núcleos físicos com 2 threads cada (hyperthreading)**: as
  4 vCPUs não são 4 núcleos inteiros. Com 2 threads o ganho é ~1,7×; de 2 para 4 quase não melhora. Mas o
  controle chega a 3,7× na mesma máquina, então o hyperthreading sozinho não explica: a hipótese é que código
  do interpretador (muito acesso à memória, contagem de referências) aproveita pouco o núcleo "irmão", e o
  código em C do `hashlib` aproveita bem. **Isso é hipótese, não medimos.** Responder assim na defesa.

**Q4 · Memória.** Sem GIL, o pico de memória do processo é **4 a 6 %** maior (cerca de 1 a 2 MiB sobre ~36 MiB),
crescendo um pouco com o nº de threads. Limitação: são processos pequenos; em aplicações grandes a
diferença pode ser outra.

**Impacto (frase-modelo; o C fecha com fonte no #18):** quem só atualizar de 3.13 para 3.14/3.15 ganha
~16–20 % de tempo de CPU em código Python puro, sem mudar código. Já o free-threading só compensa se o
código usar threads de verdade: com uma thread, custa ~11 %; com 4 threads em CPU, entrega ~2× nestas
máquinas. Quem compartilha objetos entre threads na 3.15t pode não ganhar nada.

## 5. Ameaças à validade (resumo para a defesa)

| Tipo | Ameaça | Mitigação ou limitação |
|---|---|---|
| Interna | Runners compartilhados e com CPUs diferentes (3 modelos de EPYC na coleta) | blocos + ordem sorteada + validação da variabilidade (CV mediano ≤ 1,6 %) |
| Interna | Mudança de desenho depois do piloto | feita antes da coleta completa e registrada com motivo em `bench/DESENHO.md` |
| Construto | Benchmark sintético ≠ aplicação real | suíte oficial + cargas próprias com propósito definido; limitação assumida |
| Construto | Pico de RSS de um processo pequeno ≠ memória de uma aplicação | limitação assumida no Q4 |
| Externa | 4 vCPUs (2 núcleos + hyperthreading) ≠ servidor com dezenas de núcleos | limitação assumida: o ganho sem GIL tende a crescer com mais núcleos físicos |
| Externa | Uma versão de patch por série (3.13.18, 3.14.10, 3.15.2) | versões fixadas e validadas; patches futuros podem mudar, sobretudo a regressão da 3.15t |
| Conclusão | Muitos testes | correção de Holm sobre a família inteira + tamanho do efeito, não só p-valor |
| Conclusão | Análise exploratória (interação tripla) decidida depois dos dados | apresentada como exploratória; o modelo planejado foi mantido |

## 6. O que veio dos labs anteriores

| Lab | O que reaproveitamos |
|---|---|
| Lab01 | Coleta automatizada e Kanban no GitHub Projects |
| Lab02 | Desenho com tratamentos e controle |
| Lab04 | Escolha do teste de hipótese, tamanho do efeito e dashboard gerado por código (`build.py`) |
