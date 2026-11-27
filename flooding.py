"""Busca por inundação (estilo Gnutella) para comparar com o roteamento do Pastry.

Somente biblioteca padrão. Usa os mesmos nós e as mesmas buscas da simulação do
Pastry, mas numa rede não estruturada: cada nó conhece alguns vizinhos sorteados,
sem nenhuma relação com os IDs.
"""

from collections import deque
import random

if __package__:
    from .simulation import Network, integer
else:
    from simulation import Network, integer


class UnstructuredNetwork:
    """Grafo aleatório conexo sobre os mesmos IDs de uma rede Pastry."""

    def __init__(self, ids, degree=4, seed=42):
        self.degree = integer(degree, "Grau", 1, 32)
        integer(seed, "Semente", 0, 2**32 - 1)
        self.ids = sorted(ids)
        if not self.ids:
            raise ValueError("Lista de nós vazia.")
        rng = random.Random(seed)
        self.neighbors = {node_id: set() for node_id in self.ids}
        order = self.ids[:]
        rng.shuffle(order)
        # Árvore aleatória primeiro, para garantir que o grafo seja conexo.
        for index in range(1, len(order)):
            self._link(order[index], order[rng.randrange(index)])
        # Depois, ligações extras até cada nó ter aproximadamente `degree` vizinhos.
        target = min(self.degree, len(self.ids) - 1)
        for node_id in order:
            attempts = 0
            while len(self.neighbors[node_id]) < target and attempts < 50:
                self._link(node_id, rng.choice(self.ids))
                attempts += 1

    def _link(self, a, b):
        if a != b:
            self.neighbors[a].add(b)
            self.neighbors[b].add(a)

    def flood(self, source, target, ttl):
        """Inunda a partir de `source` até o TTL acabar.

        Como no Gnutella, cada nó repassa a busca uma única vez a todos os vizinhos,
        exceto quem a enviou, e descarta cópias repetidas. A inundação não para quando
        o alvo é encontrado, porque nenhum nó sabe que outro já respondeu. Cada envio
        conta como uma mensagem, inclusive os que chegam a nós que já viram a busca.
        """
        integer(ttl, "TTL", 0, 64)
        if source not in self.neighbors:
            raise ValueError("O nó de origem não pertence à rede.")
        seen = {source: 0}
        queue = deque([(source, None, ttl)])
        messages = 0
        while queue:
            node_id, sender, remaining = queue.popleft()
            if remaining == 0:
                continue
            for other in self.neighbors[node_id]:
                if other == sender:
                    continue
                messages += 1
                if other not in seen:
                    seen[other] = seen[node_id] + 1
                    queue.append((other, node_id, remaining - 1))
        return {"found": target in seen, "hops": seen.get(target),
                "messages": messages, "reached": len(seen)}


def compare(sizes=(10, 100, 1000), ttls=(2, 4, 7), degree=4, samples=200,
            seed=42, base=16, leaf_size=2):
    """Mesmos nós e mesmos pares (origem, chave) nas duas redes.

    O alvo da inundação é o nó que o Pastry considera responsável pela chave, como
    se o objeto procurado estivesse guardado nele. No Pastry, cada salto é uma
    mensagem.
    """
    integer(samples, "Amostras", 1, 1000)
    if not isinstance(sizes, (list, tuple)) or not 1 <= len(sizes) <= 10:
        raise ValueError("Informe de 1 a 10 tamanhos de rede.")
    if not isinstance(ttls, (list, tuple)) or not 1 <= len(ttls) <= 10:
        raise ValueError("Informe de 1 a 10 valores de TTL.")
    rows = []
    for n in sorted(set(sizes)):
        net = Network(n=n, base=base, leaf_size=leaf_size, seed=seed)
        graph = UnstructuredNetwork(net.ids, degree=degree, seed=seed)
        rng = random.Random(seed + n)
        searches = []
        for _ in range(samples):
            source, key = rng.choice(net.ids), rng.randrange(net.space)
            searches.append((source, net.route(source, key)))
        pastry = [route["hops"] for _, route in searches]
        # Confere cada rota com a força bruta, em vez de supor que o Pastry acertou.
        correct = sum(route["responsible"] == net.responsible(route["key"])
                      for _, route in searches)
        row = {"n": n, "pastry_messages": sum(pastry) / samples,
               "pastry_max": max(pastry), "pastry_success": correct / samples,
               "flooding": []}
        for ttl in sorted(set(ttls)):
            results = [graph.flood(source, route["responsible"], ttl)
                       for source, route in searches]
            row["flooding"].append({
                "ttl": ttl,
                "messages": sum(r["messages"] for r in results) / samples,
                "success": sum(r["found"] for r in results) / samples,
                "reached": sum(r["reached"] for r in results) / samples,
            })
        rows.append(row)
    return {"seed": seed, "samples": samples, "degree": degree, "base": base,
            "rows": rows}
