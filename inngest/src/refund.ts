import { Inngest } from "inngest";
import * as cs from "countersignatory";

export const inngest = new Inngest({ id: "countersignatory-example-refunds" });

// How long the refund waits for your own approver before the fallback runs.
const APPROVAL_TIMEOUT = process.env.APPROVAL_TIMEOUT ?? "30s";
// The most this example will agree to pay for one human Check, in USD.
const MAX_PRICE = 1.25;
// The deadline given to the human, from payment to answer. 24 hours.
const CHECK_SLA_SECONDS = 86400;
// Off unless you say so. With it off the fallback prices the Check and stops.
const ORDERING = process.env.COUNTERSIGNATORY_ORDER === "1";

type RefundRequested = { refundId: string; customerId: string; amount: number; reason: string };

export const refundApproval = inngest.createFunction(
  { id: "refund-approval", triggers: [{ event: "refund/requested" }] },
  async ({ event, step }) => {
    const refund = event.data as RefundRequested;

    // Resolves with the matching event, or with null when the timeout passes.
    const decision = await step.waitForEvent("wait-for-approval", {
      event: "refund/approval.decided",
      timeout: APPROVAL_TIMEOUT,
      if: "async.data.refundId == event.data.refundId",
    });

    if (decision) {
      if (decision.data.approved !== true) return { status: "rejected", refundId: refund.refundId };
      await step.run("send-refund", async () => {
        // Your payment provider goes here. The example only logs.
        console.log(`refund ${refund.refundId}: sent $${refund.amount} to customer ${refund.customerId}`);
      });
      return { status: "refunded", refundId: refund.refundId };
    }

    // Nobody answered. The refund is not sent on this branch, whatever happens below.
    const humanCheck = await step.run("price-human-check", async () => {
      try {
        const q = await cs.quote({ task: "approval", tier: "check", sla: CHECK_SLA_SECONDS, maxPrice: MAX_PRICE });
        const priced = {
          market: q.market.id,
          price: q.unit_price,
          currency: q.currency,
          would_clear: q.would_clear,
          quote_id: q.quote_id,
        };
        if (!ORDERING) {
          return { ...priced, ordered: false, note: "Set COUNTERSIGNATORY_ORDER=1 to place the order. Nothing was ordered or charged." };
        }

        // Places the order and nothing more. order() never pays: a person opens
        // checkout_url, or an agent with a wallet pays at x402_pay_url.
        const o = await cs.order({
          market: "check.general",
          template: "approval",
          sla: CHECK_SLA_SECONDS,
          maxPrice: MAX_PRICE,
          input: {
            action: `Send the refund of $${refund.amount} to customer ${refund.customerId}`,
            context: refund.reason,
          },
        });
        return {
          ...priced,
          ordered: true,
          order_id: o.id,
          order_status: o.status,
          price: o.price,
          pay_by: o.pay_by ?? null,
          checkout_url: o.payment_options?.card?.checkout_url ?? null,
          x402_pay_url: o.payment_options?.x402?.pay_url ?? null,
          note: "The order is unpaid. Pay at one of the two links before pay_by, then read the answer with getOrder(order_id).",
        };
      } catch (err) {
        // A refusal or an outage must not turn into a sent refund or a retry storm.
        if (err instanceof cs.CountersignatoryError) {
          return { ordered: false, error: { code: err.code, message: err.message } };
        }
        throw err;
      }
    });

    const held = { status: "held", refundId: refund.refundId, reason: `no approval within ${APPROVAL_TIMEOUT}`, human_check: humanCheck };
    await step.run("log-held", async () => console.log(`refund ${refund.refundId}: held`, JSON.stringify(held, null, 2)));
    return held;
  }
);
