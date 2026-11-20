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

## 4. Resultados e como interpretá-los ⏳

Será preenchido depois da coleta completa: o que cada gráfico mostra, os números principais e a frase de
impacto.

## 5. Ameaças à validade (resumo para a defesa) ⏳

| Tipo | Ameaça | Mitigação |
|---|---|---|
| Interna | Runners compartilhados e com CPUs diferentes | blocos + ordem sorteada + validação da variabilidade |
| Construto | Benchmark sintético ≠ aplicação real | suíte oficial + cargas próprias com propósito definido; limitação assumida |
| Externa | 4 vCPUs ≠ servidor com dezenas de núcleos | limitação assumida: o ganho sem GIL tende a crescer com mais núcleos |
| Conclusão | Muitos testes | correção de Holm + tamanho do efeito, não só p-valor |

## 6. O que veio dos labs anteriores

| Lab | O que reaproveitamos |
|---|---|
| Lab01 | Coleta automatizada e Kanban no GitHub Projects |
| Lab02 | Desenho com tratamentos e controle |
| Lab04 | Escolha do teste de hipótese, tamanho do efeito e dashboard gerado por código (`build.py`) |
