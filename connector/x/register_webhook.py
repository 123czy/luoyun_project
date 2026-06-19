#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Register X Account Activity webhook and subscription."""
import argparse
import json
import sys

sys.path.append(".")

from conf.config import CONF
from connector.x.x_api import XAPI, XAPIError


def main():
    parser = argparse.ArgumentParser(description="Register X Account Activity webhook")
    parser.add_argument(
        "--url",
        help="public webhook url, defaults to conf.x.webhook_public_url",
    )
    parser.add_argument(
        "--environment",
        default=None,
        help="account activity environment name, defaults to conf.x.environment_name",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list existing webhooks and subscriptions",
    )
    parser.add_argument(
        "--subscribe",
        action="store_true",
        help="subscribe the authenticated user to the newest webhook",
    )
    args = parser.parse_args()

    api = XAPI()
    environment = args.environment or CONF.get("x", {}).get("environment_name", "prod")

    try:
        if args.list:
            webhooks = api.list_webhooks(environment)
            subscriptions = api.list_subscriptions(environment)
            print(json.dumps({"webhooks": webhooks, "subscriptions": subscriptions}, ensure_ascii=False, indent=2))
            return

        webhook_url = args.url or CONF.get("x", {}).get("webhook_public_url")
        if not webhook_url:
            raise SystemExit("webhook url is required via --url or conf.x.webhook_public_url")

        created = api.register_webhook(webhook_url, environment)
        print(json.dumps(created, ensure_ascii=False, indent=2))

        if args.subscribe:
            webhook_id = created.get("id") or created.get("webhook_id")
            if not webhook_id and isinstance(created, list) and created:
                webhook_id = created[0].get("id")
            if not webhook_id:
                webhooks = api.list_webhooks(environment)
                items = webhooks if isinstance(webhooks, list) else webhooks.get("data", [])
                if items:
                    webhook_id = items[-1].get("id")
            if not webhook_id:
                raise SystemExit("unable to determine webhook_id for subscription")
            subscribed = api.subscribe_account_activity(webhook_id, environment)
            print(json.dumps(subscribed, ensure_ascii=False, indent=2))
    except XAPIError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
