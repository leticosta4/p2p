# Pastry — laboratório de redes peer-to-peer

Simulador didático do roteamento do **Pastry**, uma das camadas de *routing overlay*
usadas em sistemas peer-to-peer de terceira geração. Trabalho prático da disciplina de
Sistemas Distribuídos, baseado no capítulo 10 (Sistemas Peer-to-Peer) de Coulouris
et al.

**Grupo:** Cibele Sacramento, Letícia Almeida, Samuel de Jesus e Sophia Lima.

**O que a simulação mostra:** cada nó encaminha uma busca usando apenas o que conhece
localmente, ou seja, sua tabela de roteamento e seu Leaf Set. Não existe índice
central, ao contrário do Napster. Mesmo assim, a busca chega ao nó responsável pela
chave em O(log N) saltos.

**O que ela não é:** uma rede de processos distribuídos reais. Todos os nós existem
dentro de um único processo Python, e algumas partes do protocolo foram simplificadas
(veja [Limitações e simplificações](#limitações-e-simplificações)).

O projeto tem três peças separadas: núcleo Python puro, API Flask e página HTML/JS.
**O Python decide todos os saltos e calcula todas as métricas.** O navegador recebe
nós e caminhos prontos, desenha o SVG e percorre a lista na animação.

## Executar

Na raiz do repositório, com Python 3.10 ou superior:

```bash
python3 -m venv .venv               # somente se ainda não existir
source .venv/bin/activate           # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Abra **http://127.0.0.1:5000**. Também é possível executar
`python -m app` ou escolher outra porta com `--port 5055`.
Se o ambiente existente não tiver pip, execute `python -m ensurepip --upgrade`.
O `requirements.txt` inclui Flask.

Depois de instalar Flask, a apresentação funciona sem internet: CSS, JavaScript,
fontes do sistema, anel SVG e tutorial são locais. Nenhuma CDN é necessária.

## Usando o simulador

1. **Como usar?** abre um tutorial de sete etapas sobre o anel, os controles, os
   prefixos e a saída de nós.
2. A página começa com 32 nós. Altere a quantidade e clique em **Criar rede**. Base,
   tamanho do Leaf Set e semente ficam em **Configurações avançadas**. A semente
   padrão é 42; troque-a para gerar outros IDs.
3. Escolha a origem (no campo ou clicando no anel) e uma chave hexadecimal entre
   `0000` e `FFFF`, depois clique em **Buscar chave**. **Sortear** escolhe uma chave
   e já faz a busca.
4. Percorra a rota com **Próximo salto**, **Anterior** ou **Animar busca**. O salto 0
   é a origem, e o total de saltos conta transmissões, não nós visitados.
5. A coluna **Como chegou** mostra o mecanismo de cada salto. **Tabela** é a célula do
   próximo dígito da chave. **Leaf Set** é usado quando a chave já está entre os
   vizinhos do nó. **Fallback** é o caso raro de célula vazia, em que o nó escolhe um
   contato conhecido mais próximo da chave. O prefixo em negrito é contado em dígitos
   da base escolhida.
6. Em **Para explorar mais**, inspecione a tabela e os vizinhos da origem ou remova
   uma parte dos nós para ver a rede depois da saída deles.

## Núcleo e decisões de modelagem

- IDs são os 16 bits menos significativos do SHA-1 de nomes no formato
  `no-índice-sufixo`. O sufixo é pseudoaleatório, controlado pela semente.
  Colisões geram outro nome até obter um ID livre.
- Distância circular: `min(abs(a-b), 65536-abs(a-b))`. Em empate, vence o menor ID.
  Assim, `FFFF` e `0000` têm distância 1.
- Cada nó guarda os L predecessores e L sucessores no anel. Em redes pequenas,
  as duas listas podem se sobrepor; não incluem o próprio nó.
- Cada célula da tabela aponta para um nó com o prefixo e o próximo dígito
  correspondentes. Entre os candidatos, escolhemos o de menor distância circular ao
  nó local, com desempate pelo ID.
- No roteamento, primeiro é verificado o intervalo circular do Leaf Set. Dentro
  dele, escolhe-se o mais próximo entre os vizinhos e o próprio nó. Fora dele,
  consulta-se a célula do próximo dígito da chave. Se estiver vazia, busca-se nos
  contatos locais um prefixo pelo menos tão longo e uma distância menor (ou empate
  de distância resolvido pelo ID). A ausência de progresso é tratada como erro.
- A busca termina localmente quando o próprio nó é o melhor candidato no intervalo
  do Leaf Set. **O oráculo global `responsible()` não é usado pelo roteador**;
  existe apenas para conferência por força bruta nos testes.
- O experimento usa os mesmos IDs e os mesmos pares `(origem, chave)` para cada
  base em cada N. A semente também fixa quais nós são removidos na simulação de
  saída de nós.

## Limitações e simplificações

O modelo é inspirado no Pastry de Rowstron e Druschel (ver [Referências](#referências)),
com as simplificações abaixo para manter o foco no roteamento.

- **Simulação em um único processo.** Os nós são estruturas de dados no mesmo
  programa Python. Não há troca de mensagens por rede, sockets ou concorrência.
- **Tabelas montadas de forma onisciente.** Na construção da rede, as tabelas e os
  Leaf Sets são preenchidos com uma visão global de todos os nós. No Pastry real,
  cada nó monta o próprio estado ao entrar na rede, por meio da mensagem de *join*.
  O roteamento, por outro lado, usa somente o estado local de cada nó.
- **Proximidade por ID, não por rede.** O Pastry escolhe as entradas da tabela pela
  latência física. Aqui o critério é a distância circular entre IDs.
- **Saída de nós por reconstrução.** A remoção de nós é feita em lote e seguida de uma
  nova montagem onisciente. Não há detecção de falhas, reparo descentralizado das
  tabelas nem entrega de mensagens durante as falhas.
- **Sem armazenamento de dados.** A simulação encontra o nó responsável por uma chave,
  mas não guarda nem recupera objetos nesse nó (não há `put`/`get` nem replicação).
- **Espaço de IDs reduzido.** Os IDs têm 16 bits, em vez dos 128 bits do Pastry, e a
  rede tem até 1.000 nós.
- **Sem comparação com outros modelos.** Não há comparação com a busca por inundação
  do Gnutella.

## Experimento sem servidor ou navegador

Somente a biblioteca padrão é necessária:

```bash
python3 experiment.py --samples 300 --seed 42
python3 experiment.py --bases 2 4 --sizes 10 100 1000 --json
```

O comando imprime média, máximo e `log_b(N)` ou retorna os dados em JSON. O
experimento não aparece na página; ele roda pelo terminal ou pela rota
`POST /api/experiment`.

## Testes

Na raiz:

```bash
# Só o núcleo: não precisa instalar Flask.
python3 -m unittest discover -s tests -p 'test_simulation.py' -v

# Núcleo + API, com Flask instalado no ambiente.
python -m unittest discover -s tests -v
```

A suíte compara mais de 8 mil rotas aleatórias com força bruta e percorre
exaustivamente chaves em pequenos anéis. Confere circularidade, empate, ausência
de ciclos, IDs únicos, estrutura das tabelas, fallback, semente e churn. Também
verifica que as rotas testadas não ultrapassam `número de dígitos + 2`; essa é uma
verificação empírica da simulação, não uma prova de limite universal.
O oráculo é substituído por uma função que falha durante as buscas dos testes,
para impedir que o roteador dependa acidentalmente dele.

Os testes da API cobrem parâmetros inválidos, erros JSON, isolamento de redes,
expiração, inspeção, sorteio reproduzível, experimento e busca após remoções,
usando o [cliente de testes do Flask](https://flask.palletsprojects.com/en/stable/testing/).

## Arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| `simulation.py` | IDs, distância, tabelas, Leaf Set, roteamento, churn e experimento |
| `experiment.py` | Interface de linha de comando do experimento |
| `app.py` | Validação HTTP, registro de redes e entrega da página |
| `templates/index.html` | Página única em português |
| `static/app.js` | Controles, requisições, SVG e reprodução da rota recebida |
| `static/style.css` | Layout responsivo e estilos |
| `tests/` | Conferência do núcleo e da API |

## API

Todas as operações POST recebem um objeto JSON. Erros de entrada retornam HTTP
400 com `{"error": "mensagem"}`. Rede inexistente ou expirada retorna 404.

| Método e caminho | Corpo / resultado |
| --- | --- |
| `POST /api/networks` | `{n, base, leaf_size, seed}` → `network_id` e lista de nós |
| `POST /api/route` | `{network_id, source, key}` → chave, responsável, saltos e caminho |
| `GET /api/networks/<id>/nodes/<node_id>` | Tabela e Leaf Set do nó |
| `POST /api/experiment` | `{sizes, bases, samples, seed, leaf_size}` → séries de médias, máximos e logaritmos |
| `POST /api/churn` | `{network_id, percent, seed}` → nova rede e IDs removidos |

`source` é um ID inteiro retornado na lista de nós. `key` pode ser um inteiro ou
uma string hexadecimal; `null` ou string vazia sorteiam uma chave no Python usando
`random_seed` (ou a semente da rede). As respostas incluem a representação na base
selecionada, a hexadecimal e a posição normalizada no anel para o desenho.

N vai de 1 a 1.000, Leaf Set de 1 a 8 por lado na API,
amostras de 1 a 1.000 por ponto e até 10 tamanhos por experimento. São mantidas
até 32 redes em memória por processo, com descarte da menos recentemente usada.
Reiniciar o servidor remove esse estado.

## Referências

- COULOURIS, G.; DOLLIMORE, J.; KINDBERG, T.; BLAIR, G. *Sistemas Distribuídos:
  Conceitos e Projeto*. 5. ed. Porto Alegre: Bookman, 2013. Cap. 10: Sistemas
  Peer-to-Peer.
- ROWSTRON, A.; DRUSCHEL, P. [Pastry: Scalable, decentralized object location and
  routing for large-scale peer-to-peer systems](https://www.microsoft.com/en-us/research/publication/pastry-scalable-distributed-object-location-and-routing-for-large-scale-peer-to-peer-systems/).
  In: *Middleware 2001*, LNCS 2218, p. 329–350. Springer, 2001.
