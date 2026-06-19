#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnose X API credentials and portal enrollment."""
import json
import sys

sys.path.append(".")

from conf.config import CONF
from connector.x.x_api import XAPI, XAPIError


def mask(value):
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def main():
    x_conf = CONF.get("x", {})
    required = ["api_key", "api_secret", "access_token", "access_token_secret"]
    missing = [key for key in required if not x_conf.get(key) or str(x_conf[key]).startswith("your_")]
    if missing:
        print("config missing:", ", ".join(missing))
        sys.exit(1)

    print("configured keys:")
    for key in required:
        print(f"  {key}: {mask(x_conf.get(key))}")

    api = XAPI()

    print("\n[1/3] v2 GET /users/me")
    try:
        me = api.get_me()
        print(json.dumps(me, ensure_ascii=False, indent=2))
        print("\nOK: v2 API is enrolled. You can use post_tweet and the connector.")
        return
    except XAPIError as exc:
        print(exc)
        hint = exc.portal_hint()
        if hint:
            print("\n" + hint)
            client_id = (exc.response or {}).get("client_id")
            if client_id:
                print(
                    f"\n当前 App ID = {client_id} 仍未开通 v2。\n"
                    "你的截图若显示「Apps in Free · DEPRECATED」，说明仍在旧 Free 体系，"
                    "新建 App 也无效。\n"
                    "必须改到 Pay-Per-Use 控制台：https://console.x.com\n"
                    "  → 开通计费 + 购买 Credits\n"
                    "  → 在 console 内新建 App\n"
                    "  → 用新四件套更新 conf/config.json"
                )

    print("\n[2/3] v1.1 account/verify_credentials (OAuth sanity check)")
    try:
        v1 = api.verify_credentials_v1()
        print(
            json.dumps(
                {
                    "id": v1.get("id_str") or v1.get("id"),
                    "username": v1.get("screen_name"),
                    "name": v1.get("name"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(
            "\nOAuth credentials are valid, but v2 is NOT enrolled.\n"
            "Posting tweets uses v2 POST /tweets and will fail until the portal fix above is done."
        )
    except XAPIError as exc:
        print(exc)
        print("\nOAuth credentials themselves may be wrong. Regenerate all four keys in the portal.")

    print("\n[3/3] v2 POST /tweets dry-run expectation")
    print("After portal fix, rerun:")
    print("  python3 connector/x/verify_setup.py")
    print("  python3 connector/x/post_tweet.py \"test tweet\"")


if __name__ == "__main__":
    main()
