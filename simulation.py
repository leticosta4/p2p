"""Núcleo independente: apenas biblioteca padrão, sem HTTP ou interface."""

from bisect import bisect_left
from dataclasses import dataclass
from hashlib import sha1
from math import ceil, log
import random

DIGITS = "0123456789ABCDEF"
BASES = (2, 4, 16)


def circular_distance(a: int, b: int, space: int) -> int:
    delta = abs(a - b) % space
    return min(delta, space - delta)


def shared_prefix(a: str, b: str) -> int:
    for i, (left, right) in enumerate(zip(a, b)):
        if left != right:
            return i
    return min(len(a), len(b))


def integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} deve ser um inteiro entre {minimum} e {maximum}.")
    return value


@dataclass(frozen=True)
class Node:
    id: int
    name: str


class Network:
    def __init__(self, n=64, base=16, leaf_size=2, seed=42, bits=16, *, nodes=None):
        if type(base) is not int or base not in BASES:
            raise ValueError("A base deve ser 2, 4 ou 16.")
        self.bits = integer(bits, "Bits", 4, 16)
        self.base = base
        self.digit_bits = base.bit_length() - 1
        if bits % self.digit_bits:
            raise ValueError("Bits deve ser múltiplo do tamanho do dígito da base.")
        self.width = bits // self.digit_bits
        self.space = 1 << bits
        self.leaf_size = integer(leaf_size, "Leaf Set por lado", 1, 8)
        self.seed = integer(seed, "Semente", 0, 2**32 - 1)
        if nodes is None:
            integer(n, "N", 1, min(1000, self.space))
            rng = random.Random(seed)
            generated = {}
            while len(generated) < n:
                name = f"no-{len(generated)}-{rng.getrandbits(64):016x}"
                node_id = int.from_bytes(sha1(name.encode()).digest(), "big") & (self.space - 1)
                generated.setdefault(node_id, Node(node_id, name))
            nodes = list(generated.values())
        if not nodes or len(nodes) > min(1000, self.space):
            raise ValueError("Lista de nós vazia ou grande demais.")
        self.nodes = {node.id: node for node in nodes}
        if len(self.nodes) != len(nodes):
            raise ValueError("IDs de nós duplicados.")
        for node_id in self.nodes:
            integer(node_id, "ID", 0, self.space - 1)
        self.ids = sorted(self.nodes)
        self.labels = {node_id: self.digits(node_id) for node_id in self.ids}
        self.leaves = {}
        self.tables = {}
        self._build()

    def digits(self, value):
        return "".join(DIGITS[(value >> shift) & (self.base - 1)]
                       for shift in range(self.bits - self.digit_bits, -1, -self.digit_bits))

    def hex_id(self, value):
        return f"{value:0{ceil(self.bits / 4)}X}"

    def _rank(self, node_id, key):
        # Empates sempre escolhem o menor ID, inclusive na fronteira do anel.
        return circular_distance(node_id, key, self.space), node_id

    def responsible(self, key):
        """Oráculo por força bruta: usado nos testes, nunca para decidir saltos."""
        integer(key, "Chave", 0, self.space - 1)
        return min(self.ids, key=lambda node_id: self._rank(node_id, key))

    def _build(self):
        # Visão onisciente somente na montagem. Buckets evitam comparar todos os pares.
        buckets = {}
        for node_id in self.ids:
            label = self.labels[node_id]
            for length in range(1, self.width + 1):
                buckets.setdefault(label[:length], []).append(node_id)
        n = len(self.ids)
        for index, node_id in enumerate(self.ids):
            self.leaves[node_id] = {
                "left": [self.ids[(index - k) % n] for k in range(1, min(n, self.leaf_size + 1))],
                "right": [self.ids[(index + k) % n] for k in range(1, min(n, self.leaf_size + 1))],
            }
            label = self.labels[node_id]
            table = []
            for length in range(self.width):
                row = []
                for digit in DIGITS[:self.base]:
                    group = buckets.get(label[:length] + digit, [])
                    if digit == label[length] or not group:
                        row.append(None)
                    else:
                        position = bisect_left(group, node_id)
                        candidates = (group[position % len(group)], group[position - 1])
                        row.append(min(candidates, key=lambda other: self._rank(other, node_id)))
                table.append(row)
            self.tables[node_id] = table

    def _in_leaf_range(self, node_id, key):
        if len(self.ids) <= 2 * self.leaf_size + 1:
            return True
        leaf = self.leaves[node_id]
        left, right = leaf["left"][-1], leaf["right"][-1]
        return (key - left) % self.space <= (right - left) % self.space

    def route(self, source, key):
        integer(source, "Origem", 0, self.space - 1)
        integer(key, "Chave", 0, self.space - 1)
        if source not in self.nodes:
            raise ValueError("O nó de origem não pertence à rede ativa.")
        key_digits = self.digits(key)
        current, reason = source, "Origem"
        path, visited = [], set()
        while True:
            if current in visited:
                raise RuntimeError("Ciclo detectado no roteamento.")
            visited.add(current)
            prefix = shared_prefix(self.labels[current], key_digits)
            path.append({**self.node_data(current), "prefix_length": prefix, "reason": reason})
            leaf = self.leaves[current]
            if self._in_leaf_range(current, key):
                next_id = min({current, *leaf["left"], *leaf["right"]},
                              key=lambda other: self._rank(other, key))
                if next_id == current:
                    break
                reason = "Leaf Set"
            else:
                next_id = self.tables[current][prefix][int(key_digits[prefix], self.base)]
                reason = "Tabela"
                if next_id is None:
                    known = {node for row in self.tables[current] for node in row if node is not None}
                    known.update(leaf["left"] + leaf["right"])
                    candidates = [node for node in known
                                  if shared_prefix(self.labels[node], key_digits) >= prefix
                                  and self._rank(node, key) < self._rank(current, key)]
                    if not candidates:
                        raise RuntimeError("Nenhum vizinho permite progresso; verifique as tabelas.")
                    next_id = min(candidates, key=lambda other: self._rank(other, key))
                    reason = "Fallback"
            current = next_id
        return {"source": source, "key": key, "key_hex": self.hex_id(key),
                "key_digits": key_digits, "key_position": key / self.space,
                "responsible": current, "responsible_hex": self.hex_id(current),
                "hops": len(path) - 1, "path": path}

    def node_data(self, node_id):
        return {"id": node_id, "hex": self.hex_id(node_id), "digits": self.labels[node_id],
                "position": node_id / self.space, "name": self.nodes[node_id].name}

    def snapshot(self):
        return {"n": len(self.ids), "base": self.base, "bits": self.bits, "width": self.width,
                "leaf_size": self.leaf_size, "seed": self.seed, "space": self.space,
                "nodes": [self.node_data(node_id) for node_id in self.ids]}

    def inspect(self, node_id):
        if node_id not in self.nodes:
            raise ValueError("Nó não encontrado.")
        return {**self.node_data(node_id), "leaf_set": self.leaves[node_id],
                "table": self.tables[node_id]}

    def remove_fraction(self, percent, seed):
        integer(percent, "Percentual", 1, 90)
        integer(seed, "Semente", 0, 2**32 - 1)
        count = min(len(self.ids) - 1, max(1, len(self.ids) * percent // 100))
        removed = sorted(random.Random(seed).sample(self.ids, count))
        removed_set = set(removed)
        survivors = [node for node_id, node in self.nodes.items() if node_id not in removed_set]
        return Network(base=self.base, leaf_size=self.leaf_size, seed=self.seed,
                       bits=self.bits, nodes=survivors), removed


def experiment(sizes=(10, 20, 50, 100, 200, 500, 1000), bases=BASES,
               samples=300, seed=42, leaf_size=2):
    integer(samples, "Amostras", 1, 1000)
    integer(seed, "Semente", 0, 2**32 - 1)
    if not isinstance(sizes, (list, tuple)) or not 1 <= len(sizes) <= 10:
        raise ValueError("Informe de 1 a 10 tamanhos de rede.")
    if not isinstance(bases, (list, tuple)) or not 1 <= len(bases) <= 3:
        raise ValueError("Informe de 1 a 3 bases.")
    for n in sizes:
        integer(n, "N", 1, 1000)
    if any(type(base) is not int or base not in BASES for base in bases):
        raise ValueError("As bases permitidas são 2, 4 e 16.")
    series = []
    for base in dict.fromkeys(bases):
        points = []
        for n in sorted(set(sizes)):
            net = Network(n=n, base=base, leaf_size=leaf_size, seed=seed)
            rng = random.Random(seed + n)
            hops = [net.route(rng.choice(net.ids), rng.randrange(net.space))["hops"]
                    for _ in range(samples)]
            points.append({"n": n, "mean": sum(hops) / samples, "max": max(hops),
                           "theoretical": log(n, base)})
        series.append({"base": base, "points": points})
    return {"seed": seed, "samples": samples, "leaf_size": leaf_size, "series": series}
