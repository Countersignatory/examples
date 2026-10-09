# Inngest: a refund that waits, then prices a human

Written by the founder of Countersignatory. One market is live: a screened human answers an approval for $1.25, refunded if not answered in time.

`src/refund.ts` holds one function. It waits on `step.waitForEvent` for `refund/approval.decided`. If the event arrives, the refund is sent or rejected. If the timeout passes, `waitForEvent` returns `null`, and inside `step.run` the function prices a human Check. The refund stays held on that branch.

## Run it

Node 20 or later.

1. Install: `npm ci`
2. Start the app: `npm run dev`
3. In a second terminal, start the Inngest dev server: `npx inngest-cli@latest dev -u http://localhost:3000/api/inngest`
4. In a third, request a refund:

```
curl -X POST http://localhost:8288/e/dev -H 'content-type: application/json' -d '{"name":"refund/requested","data":{"refundId":"rf_1001","customerId":"1182","amount":40,"reason":"The item arrived broken. Policy allows refunds under $50."}}'
```

Wait 30 seconds without approving. The app's terminal prints the held refund with the price of the Check, and the run shows the same at http://localhost:8288.

To approve in time, send this before the timeout:

```
curl -X POST http://localhost:8288/e/dev -H 'content-type: application/json' -d '{"name":"refund/approval.decided","data":{"refundId":"rf_1001","approved":true}}'
```

## Settings

| Variable | Default | What it does |
|---|---|---|
| `APPROVAL_TIMEOUT` | `30s` | How long `waitForEvent` waits for your approver. |
| `COUNTERSIGNATORY_ORDER` | unset | Set to `1` to place an order on the timeout branch. Unset, the Check is priced and nothing is ordered. |
| `COUNTERSIGNATORY_BASE_URL` | `https://countersignatory.com` | The server the client calls. |
| `PORT` | `3000` | The port the Express app listens on. |

## With ordering on

`COUNTERSIGNATORY_ORDER=1 npm run dev` makes the timeout branch call `cs.order()`. The run returns `order_id`, `checkout_url` for a person with a card, `x402_pay_url` for an agent with a wallet, and `pay_by`. Nothing is paid by this example: the order is unpaid until someone pays it at one of the two links, and it lapses after 30 minutes if nobody does. Once it is paid and answered, read the answer with `getOrder(order_id)` and release or cancel the refund yourself.

An identical order from the same key, while the first is still unpaid, returns that same order and does not make a second one. Running the example twice with the same refund gives one `order_id`.

A refused or failed order is returned as `error` with its code and reason, and the refund stays held.
