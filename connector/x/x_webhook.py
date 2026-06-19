# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import logging
import sys
import traceback

from flask import Flask, jsonify, request

sys.path.append(".")

from conf.config import CONF
from connector.x.x_ingest import ingest_activity_payload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def build_crc_response(crc_token):
    consumer_secret = CONF.get("x", {}).get("api_secret", "")
    digest = hmac.new(
        consumer_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return {"response_token": "sha256=" + base64.b64encode(digest).decode("utf-8")}


def get_webhook_path():
    return CONF.get("x", {}).get("webhook_path", "/x/webhook")


@app.route(get_webhook_path(), methods=["GET"])
def webhook_crc():
    crc_token = request.args.get("crc_token")
    if not crc_token:
        return jsonify({"status": "error", "message": "missing crc_token"}), 400
    logger.info("received crc challenge")
    return jsonify(build_crc_response(crc_token))


@app.route(get_webhook_path(), methods=["POST"])
def webhook_events():
    if not request.is_json:
        logger.warning("webhook payload is not json")
        return jsonify({"status": "error", "message": "payload must be json"}), 400

    payload = request.get_json()
    logger.info("received webhook event keys: %s", list(payload.keys()))

    try:
        ingested = ingest_activity_payload(payload, source="webhook")
        return jsonify({"status": "success", "ingested": ingested}), 200
    except Exception:
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": "failed to ingest webhook event"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "x_webhook"}), 200


if __name__ == "__main__":
    host = CONF.get("x", {}).get("webhook_host", "0.0.0.0")
    port = int(CONF.get("x", {}).get("webhook_port", 8081))
    debug = bool(CONF.get("x", {}).get("webhook_debug", False))
    logger.info("starting x webhook on %s:%s%s", host, port, get_webhook_path())
    app.run(host=host, port=port, debug=debug)
