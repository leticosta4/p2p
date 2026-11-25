# Pastry — laboratório de redes peer-to-peer

Simulador didático com três peças separadas: núcleo Python puro, API Flask e página
HTML/JS. **O Python decide todos os saltos e calcula todas as métricas.** O navegador
recebe nós e caminhos prontos, desenha o SVG e percorre a lista na animação.

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

## Usar na apresentação

1. Clique em **Como usar?** para abrir o tutorial sobreposto de sete etapas. Ele
   explica o objetivo da simulação, o anel, os controles, os prefixos e a saída de
   nós. Use **Próxima etapa**, **Voltar** ou as setas do teclado. Feche com o botão
   **Fechar**, com Esc ou conclua em **Começar a simulação**. A animação pausa ao
   abrir o tutorial; o restante da página fica sem interação até ele ser fechado.
2. A página começa com uma rede de 32 nós. Para alterar a quantidade, use o campo
   numérico ou o slider e clique em **Criar rede**. Base, Leaf Set e semente ficam
   em **Configurações avançadas**. A semente padrão é 42; altere-a para outros IDs.
3. Selecione a origem pelo campo ou clicando no anel. Digite uma chave
   **hexadecimal** entre `0000` e `FFFF` e clique em **Buscar chave**, ou use
   **Sortear**, que já calcula a nova busca.
4. Use **Próximo salto**, **Anterior**, **Animar busca** e **Voltar ao início**
   abaixo do anel. A explicação acompanha o salto exibido. O salto 0 é a origem;
   a contagem de saltos é o número de transmissões, não de nós visitados.
5. Veja a coluna **Como chegou**: **Tabela**, **Leaf Set** ou **Fallback**. O prefixo em
   negrito é medido em dígitos da base selecionada. IDs no anel e no seletor continuam
   em hexadecimal; a tabela de saltos usa 16 dígitos na base 2, 8 na base 4 ou 4 na base 16.
6. Em **Para explorar mais**, abra a inspeção para ver a tabela e os vizinhos da
   origem, ou teste a saída de nós. Se a origem sair, uma origem sobrevivente será
   selecionada e isso aparecerá no resultado.

O gráfico de crescimento não faz parte da página. O experimento continua
disponível pelo terminal e pela API para uso separado.

## Núcleo e decisões de modelagem

- IDs são os 16 bits menos significativos do SHA-1 de nomes no formato
  `no-índice-sufixo`. O sufixo é pseudoaleatório, controlado pela semente.
  Colisões geram outro nome até obter um ID livre.
- Distância circular: `min(abs(a-b), 65536-abs(a-b))`. Em empate, vence o menor ID.
  Assim, `FFFF` e `0000` têm distância 1.
- Cada nó guarda os L predecessores e L sucessores no anel. Em redes pequenas,
  as duas listas podem se sobrepor; não incluem o próprio nó.
- As tabelas são **montadas de forma onisciente**, usando toda a rede. Cada célula
  aponta para um nó com o prefixo e o próximo dígito correspondentes. Entre
  candidatos, escolhemos o de menor distância circular ao nó local, com desempate
  pelo ID. Isso é uma simplificação; não há medição de latência física.
- No roteamento, primeiro é verificado o intervalo circular do Leaf Set. Dentro
  dele, escolhe-se o mais próximo entre os vizinhos e o próprio nó. Fora dele,
  consulta-se a célula do próximo dígito da chave. Se estiver vazia, busca-se nos
  contatos locais um prefixo pelo menos tão longo e uma distância menor (ou empate
  de distância resolvido pelo ID). A ausência de progresso é tratada como erro.
- A busca termina localmente quando o próprio nó é o melhor candidato no intervalo
  do Leaf Set. **O oráculo global `responsible()` não é usado pelo roteador**;
  existe apenas para conferência por força bruta nos testes.
- O experimento usa os mesmos IDs e os mesmos pares `(origem, chave)` para cada
  base em cada N. A semente também fixa as remoções no bônus de churn.
- Churn é uma remoção em lote seguida de reconstrução onisciente. Não implementa
  join, manutenção descentralizada, detecção de falhas ou entrega durante falhas.
  A comparação com inundação não faz parte desta versão.

O modelo é inspirado no [Pastry, de Rowstron e Druschel](https://www.microsoft.com/en-us/research/publication/pastry-scalable-distributed-object-location-and-routing-for-large-scale-peer-to-peer-systems/),
com IDs reduzidos e as simplificações acima para facilitar a apresentação.

## Experimento sem servidor ou navegador

Somente a biblioteca padrão é necessária:

```bash
python3 experiment.py --samples 300 --seed 42
python3 experiment.py --bases 2 4 --sizes 10 100 1000 --json
```

O comando imprime média, máximo e `log_b(N)` ou retorna os dados em JSON.

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
Reiniciar o servidor remove esse estado. O programa é uma simulação local, não
uma rede de processos distribuídos reais.
