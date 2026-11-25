import unittest

from peerToPeer.app import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.testing = True
        self.client = app.test_client()

    def network(self, **kwargs):
        response = self.client.post("/api/networks", json=kwargs)
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_page_and_static_assets(self):
        for path in ("/", "/static/app.js", "/static/style.css"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_network_route_inspection_and_isolation(self):
        net = self.network(n=30, seed=42)
        other = self.network(n=10, seed=7)
        self.assertNotEqual(net["network_id"], other["network_id"])
        source = net["nodes"][0]["id"]
        response = self.client.post("/api/route", json={"network_id": net["network_id"],
                                                      "source": source, "key": "FFFF"})
        self.assertEqual(response.status_code, 200)
        route = response.get_json()
        expected = min((n["id"] for n in net["nodes"]),
                       key=lambda n: (min(abs(n - 65535), 65536 - abs(n - 65535)), n))
        self.assertEqual(route["responsible"], expected)
        self.assertEqual(route["path"][0]["id"], source)
        detail = self.client.get(f"/api/networks/{net['network_id']}/nodes/{source}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.get_json()["table"]), 4)
        payload = {"network_id": net["network_id"], "source": source, "random_seed": 70}
        self.assertEqual(self.client.post("/api/route", json=payload).json,
                         self.client.post("/api/route", json=payload).json)

    def test_churn_then_route(self):
        net = self.network(n=50)
        response = self.client.post("/api/churn", json={"network_id": net["network_id"], "percent": 40})
        self.assertEqual(response.status_code, 200)
        new = response.get_json()
        self.assertEqual(new["n"], 30)
        self.assertEqual(len(new["removed"]), 20)
        route = self.client.post("/api/route", json={"network_id": new["network_id"],
                                                  "source": new["nodes"][0]["id"], "key": "0000"})
        self.assertEqual(route.status_code, 200)
        self.assertNotIn(route.json["responsible"], new["removed"])

    def test_experiment(self):
        response = self.client.post("/api/experiment", json={"sizes": [10, 20], "samples": 30})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["series"]), 3)
        self.assertEqual([p["n"] for p in response.json["series"][0]["points"]], [10, 20])

    def test_bad_requests_and_expiration(self):
        for data in ([], {"n": 0}, {"n": 1.5}, {"base": 3}, {"seed": True}, {"leaf_size": 100}):
            response = self.client.post("/api/networks", json=data)
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.json)
        net = self.network(n=1)
        for key in ("GGGG", "10000", -1, [], True):
            response = self.client.post("/api/route", json={"network_id": net["network_id"],
                                                          "source": net["nodes"][0]["id"], "key": key})
            self.assertEqual(response.status_code, 400)
        for data in ({"samples": 0}, {"bases": [3]}, {"sizes": [1001]}, {"bases": "2"}):
            self.assertEqual(self.client.post("/api/experiment", json=data).status_code, 400)
        self.assertEqual(self.client.post("/api/networks", data="broken", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/route", json={"network_id": "missing"}).status_code, 404)
        for _ in range(32):
            self.network(n=1)
        self.assertEqual(self.client.post("/api/route", json={"network_id": net["network_id"]}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
