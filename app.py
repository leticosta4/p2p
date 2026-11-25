"""API fina e página local. Execute: python peerToPeer/app.py."""

import argparse
from collections import OrderedDict
import random
from threading import Lock
from uuid import uuid4

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

if __package__:
    from .simulation import Network, experiment, integer
else:
    from simulation import Network, experiment, integer


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    networks = OrderedDict()
    registry_lock = Lock()

    def body():
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError("Envie um objeto JSON.")
        return data

    def save(network):
        network_id = uuid4().hex
        with registry_lock:
            networks[network_id] = network
            if len(networks) > 32:
                networks.popitem(last=False)
        return {"network_id": network_id, **network.snapshot()}

    def get_network(network_id):
        if not isinstance(network_id, str):
            raise ValueError("Informe network_id.")
        with registry_lock:
            if network_id not in networks:
                return None
            networks.move_to_end(network_id)
            return networks[network_id]

    def require_network(network_id):
        network = get_network(network_id)
        if network is None:
            from werkzeug.exceptions import NotFound
            raise NotFound("Rede não encontrada ou expirada. Gere uma nova rede.")
        return network

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/networks")
    def create_network():
        data = body()
        network = Network(n=data.get("n", 64), base=data.get("base", 16),
                          leaf_size=data.get("leaf_size", 2), seed=data.get("seed", 42))
        return jsonify(save(network)), 201

    @app.get("/api/networks/<network_id>/nodes/<int:node_id>")
    def inspect_node(network_id, node_id):
        return jsonify(require_network(network_id).inspect(node_id))

    @app.post("/api/route")
    def route():
        data = body()
        network = require_network(data.get("network_id"))
        key = data.get("key")
        if key is None or key == "":
            seed = integer(data.get("random_seed", network.seed), "Semente", 0, 2**32 - 1)
            key = random.Random(seed).randrange(network.space)
        elif isinstance(key, str):
            if len(key) > 6:
                raise ValueError("Use uma chave hexadecimal entre 0000 e FFFF.")
            try:
                key = int(key, 16)
            except ValueError:
                raise ValueError("Use uma chave hexadecimal entre 0000 e FFFF.") from None
        return jsonify(network.route(data.get("source"), key))

    @app.post("/api/experiment")
    def run_experiment():
        data = body()
        return jsonify(experiment(sizes=data.get("sizes", [10, 20, 50, 100, 200, 500, 1000]),
                                  bases=data.get("bases", [2, 4, 16]),
                                  samples=data.get("samples", 300), seed=data.get("seed", 42),
                                  leaf_size=data.get("leaf_size", 2)))

    @app.post("/api/churn")
    def churn():
        data = body()
        network = require_network(data.get("network_id"))
        survivors, removed = network.remove_fraction(data.get("percent", 20),
                                                     data.get("seed", network.seed))
        return jsonify({**save(survivors), "removed": removed})

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulador Pastry local")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    create_app().run(host="127.0.0.1", port=args.port, debug=False)
