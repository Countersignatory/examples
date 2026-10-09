# Countersignatory examples

Two small programs that show one pattern: an approval step waits for your own human, and when the deadline passes with no answer, the workflow prices a human Check from [Countersignatory](https://countersignatory.com) as the fallback.

Written by the founder of Countersignatory. One market is live: a screened human answers an approval for $1.25, refunded if not answered in time.

| Folder | Framework | The wait |
|---|---|---|
| [`inngest/`](inngest/) | Inngest 4, Express, TypeScript | `step.waitForEvent` with a timeout |
| [`langgraph/`](langgraph/) | LangGraph, Python | `interrupt()` with a deadline the app keeps |

## What both do

1. A refund is requested and held for approval.
2. If your approver answers in time, the refund is sent or rejected and Countersignatory is never called.
3. If nobody answers, the workflow asks Countersignatory for the price of one human Check and stops. The refund stays held.
4. Only if you set `COUNTERSIGNATORY_ORDER=1` does it also place an order, with `order()` from the `countersignatory` package at 0.2.0, and return a card checkout link and an x402 pay link.

Neither example pays for anything. An order comes back unpaid, and it lapses after 30 minutes if nobody pays it.

## What a run sends

With ordering off, the timeout branch sends one quote request to countersignatory.com. The first time, the client takes a free key and caches it at `~/.config/countersignatory/key`. With ordering on, the action and the reason of the refund are sent as the task, and a person reads them, so put nothing in them that a stranger should not see.

Set `COUNTERSIGNATORY_BASE_URL` to point either example at another server.

MIT licence. Countersignatory Ltd.
