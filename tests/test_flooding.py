import random
import unittest

from flooding import UnstructuredNetwork, compare
from simulation import Network


def bfs_distances(graph, source):
    distances, frontier = {source: 0}, [source]
    while frontier:
        following = []
        for node_id in frontier:
            for other in graph.neighbors[node_id]:
                if other not in distances:
                    distances[other] = distances[node_id] + 1
                    following.append(other)
        frontier = following
    return distances


class FloodingTests(unittest.TestCase):
    def test_graph_is_connected_symmetric_and_reproducible(self):
        for n in (1, 2, 10, 200):
            ids = Network(n=n, seed=7).ids
            graph = UnstructuredNetwork(ids, degree=4, seed=7)
            self.assertEqual(len(bfs_distances(graph, ids[0])), n)
            for node_id, others in graph.neighbors.items():
                self.assertNotIn(node_id, others)
                for other in others:
                    self.assertIn(node_id, graph.neighbors[other])
            again = UnstructuredNetwork(ids, degree=4, seed=7)
            self.assertEqual(graph.neighbors, again.neighbors)

    def test_flood_matches_bfs_within_ttl(self):
        ids = Network(n=150, seed=3).ids
        graph = UnstructuredNetwork(ids, degree=3, seed=3)
        rng = random.Random(1)
        for _ in range(100):
            source, target = rng.choice(ids), rng.choice(ids)
            distances = bfs_distances(graph, source)
            for ttl in (0, 1, 2, 4, 8):
                result = graph.flood(source, target, ttl)
                expected = distances[target] <= ttl
                self.assertEqual(result["found"], expected)
                self.assertEqual(result["hops"], distances[target] if expected else None)
                self.assertEqual(result["reached"],
                                 sum(1 for d in distances.values() if d <= ttl))

    def test_message_count_on_known_graph(self):
        # Caminho 0 - 1 - 2 - 3: cada nó repassa a todos os vizinhos, menos ao remetente.
        graph = UnstructuredNetwork([0, 1, 2, 3], degree=1, seed=0)
        graph.neighbors = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2}}
        self.assertEqual(graph.flood(0, 3, 0)["messages"], 0)
        self.assertEqual(graph.flood(0, 3, 2)["messages"], 2)
        self.assertEqual(graph.flood(0, 3, 3), {"found": True, "hops": 3,
                                                "messages": 3, "reached": 4})
        # Triângulo: as cópias repetidas também contam como mensagens.
        graph.neighbors = {0: {1, 2}, 1: {0, 2}, 2: {0, 1}, 3: set()}
        self.assertEqual(graph.flood(0, 2, 2)["messages"], 4)

    def test_compare_uses_pastry_responsible_and_flooding_costs_more(self):
        result = compare(sizes=[200], ttls=[1, 7], samples=50, seed=5)
        row = result["rows"][0]
        self.assertEqual(row["pastry_success"], 1.0)
        low, high = row["flooding"]
        self.assertLessEqual(low["success"], high["success"])
        self.assertEqual(high["success"], 1.0)
        self.assertGreater(high["messages"], 10 * row["pastry_messages"])
        self.assertEqual(compare(sizes=[50], samples=20, seed=9),
                         compare(sizes=[50], samples=20, seed=9))

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            UnstructuredNetwork([], degree=4)
        with self.assertRaises(ValueError):
            UnstructuredNetwork([1, 2], degree=0)
        graph = UnstructuredNetwork([1, 2], degree=1)
        with self.assertRaises(ValueError):
            graph.flood(99, 1, 3)
        with self.assertRaises(ValueError):
            graph.flood(1, 2, -1)
        with self.assertRaises(ValueError):
            compare(ttls=[])


if __name__ == "__main__":
    unittest.main()
