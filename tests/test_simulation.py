import random
import unittest
from unittest.mock import patch

from simulation import Network, Node, circular_distance, experiment, shared_prefix


class SimulationTests(unittest.TestCase):
    def check_route(self, net, source, key):
        expected = net.responsible(key)
        with patch.object(net, "responsible", side_effect=AssertionError("Oráculo usado na rota")):
            result = net.route(source, key)
        self.assertEqual(result["responsible"], expected, (net.base, source, key, result))
        self.assertEqual(result["hops"], len(result["path"]) - 1)
        self.assertLessEqual(result["hops"], net.width + 2)
        self.assertEqual(len({hop["id"] for hop in result["path"]}), len(result["path"]))
        for hop in result["path"]:
            self.assertEqual(hop["prefix_length"], shared_prefix(hop["digits"], net.digits(key)))

    def test_thousands_of_routes_against_brute_force(self):
        rng = random.Random(2026)
        for base in (2, 4, 16):
            for seed in (0, 42, 99):
                for n in (1, 2, 10, 64, 200, 1000):
                    net = Network(n=n, base=base, seed=seed)
                    for _ in range(150):
                        self.check_route(net, rng.choice(net.ids), rng.randrange(net.space))

    def test_exhaustive_small_ring_and_ties(self):
        for base in (2, 4, 16):
            for ids in ([0], [0, 8], [1, 4, 7, 10, 13, 15], [0, 1, 2, 3, 4, 15], list(range(16))):
                net = Network(base=base, bits=4, leaf_size=1,
                              nodes=[Node(i, str(i)) for i in ids])
                for source in ids:
                    for key in range(16):
                        self.check_route(net, source, key)
        self.assertEqual(circular_distance(0, 65535, 65536), 1)

    def test_sha_ids_collisions_and_reproducibility(self):
        net = Network(n=16, bits=4)
        self.assertEqual(net.snapshot(), Network(n=16, bits=4).snapshot())
        self.assertEqual(len(set(net.ids)), 16)
        self.assertEqual(Network(n=50, base=2).ids, Network(n=50, base=16).ids)

    def test_tables_and_leaf_sets(self):
        for base in (2, 4, 16):
            net = Network(n=100, base=base)
            for index, node_id in enumerate(net.ids):
                self.assertEqual(net.leaves[node_id]["left"][0], net.ids[index - 1])
                self.assertEqual(net.leaves[node_id]["right"][0], net.ids[(index + 1) % 100])
                for length, row in enumerate(net.tables[node_id]):
                    for digit, candidate in enumerate(row):
                        prefix = net.labels[node_id][:length] + "0123456789ABCDEF"[digit]
                        matches = [i for i in net.ids if net.labels[i].startswith(prefix)]
                        if candidate is not None:
                            self.assertIn(candidate, matches)
                            self.assertNotEqual(candidate, node_id)
                        elif prefix != net.labels[node_id][:length + 1]:
                            self.assertEqual(matches, [])

    def test_fallback_with_missing_entry(self):
        net = Network(n=200, base=4)
        found = False
        for source in net.ids:
            key = (source + 17000) % net.space
            prefix = shared_prefix(net.labels[source], net.digits(key))
            digit = int(net.digits(key)[prefix], net.base)
            old = net.tables[source][prefix][digit]
            net.tables[source][prefix][digit] = None
            result = net.route(source, key)
            self.assertEqual(result["responsible"], net.responsible(key))
            net.tables[source][prefix][digit] = old
            if any(hop["reason"] == "Fallback" for hop in result["path"]):
                found = True
                break
        self.assertTrue(found)

    def test_churn_and_experiment(self):
        net, removed = Network(n=100).remove_fraction(25, 10)
        self.assertEqual(len(removed), 25)
        self.assertEqual(len(net.ids), 75)
        self.assertFalse(set(removed) & set(net.ids))
        for key in range(0, net.space, 997):
            self.check_route(net, net.ids[0], key)
        args = dict(sizes=[10, 30], samples=20)
        self.assertEqual(experiment(**args), experiment(**args))

    def test_validation(self):
        for kwargs in ({"n": 0}, {"n": True}, {"n": 1001}, {"base": 8},
                       {"seed": -1}, {"leaf_size": 0}, {"bits": 5, "base": 4}):
            with self.assertRaises(ValueError):
                Network(**kwargs)


if __name__ == "__main__":
    unittest.main()
