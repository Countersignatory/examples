# LangGraph: an approval with a deadline, then a priced human

Written by the founder of Countersignatory. One market is live: a screened human answers an approval for $1.25, refunded if not answered in time.

`app.py` holds one graph. The `approval` node calls `interrupt()`, which pauses the graph. `interrupt()` has no timeout of its own, so the app that drives the graph keeps the deadline: it waits for a line on the terminal, and if none comes in time it resumes the graph with `timeout`. The graph then prices a human Check. The refund stays held on that branch.

## Run it

Python 3.9 or later.

1. Make an environment: `python3 -m venv .venv && source .venv/bin/activate`
2. Install: `pip install -r requirements.txt`
3. Run: `python app.py`

Type `approve` or `reject` within 30 seconds and the refund is sent or rejected. Type nothing, and the program prints the held refund with the price of the Check.

## Settings

| Variable | Default | What it does |
|---|---|---|
| `APPROVAL_TIMEOUT` | `30` | Seconds the app waits for your approver. |
| `COUNTERSIGNATORY_ORDER` | unset | Set to `1` to place an order on the timeout branch. Unset, the Check is priced and nothing is ordered. |
| `COUNTERSIGNATORY_BASE_URL` | `https://countersignatory.com` | The server the client calls. |

## With ordering on

`COUNTERSIGNATORY_ORDER=1 python app.py` makes the timeout branch call `cs.order()`. The result carries `order_id`, `checkout_url` for a person with a card, `x402_pay_url` for an agent with a wallet, and `pay_by`. Nothing is paid by this example: the order is unpaid until someone pays it at one of the two links, and it lapses after 30 minutes if nobody does. Once it is paid and answered, read the answer with `cs.get_order(order_id)` and release or cancel the refund yourself.

A refused or failed order is returned as `error` with its code and reason, and the refund stays held.

The example uses `InMemorySaver`, so a paused graph is lost when the process exits. Use a durable checkpointer for anything real.
