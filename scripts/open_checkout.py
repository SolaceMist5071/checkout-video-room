import argparse
import json

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Open a customer checkout video session")
    parser.add_argument("--order", required=True)
    parser.add_argument("--customer", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    response = httpx.post(
        "http://127.0.0.1:8000/sessions",
        json={
            "order_id": args.order,
            "customer_id": args.customer,
            "display_name": args.name,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
