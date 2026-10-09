"""A refund that waits on a human, with a deadline the app keeps.

The graph pauses on interrupt(). interrupt() has no timeout of its own, so the
app that drives the graph keeps the deadline: if nobody answers in time it
resumes the graph with "timeout", and the graph prices a human Check from
Countersignatory. It places an order only if COUNTERSIGNATORY_ORDER=1, never
pays, and leaves the refund held either way.
"""

import json
import os
import queue
import threading
from typing import Any, Dict, Optional

import countersignatory as cs
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

# How long the app waits for your own approver before the fallback runs, in seconds.
APPROVAL_TIMEOUT = float(os.environ.get("APPROVAL_TIMEOUT", "30"))
# The most this example will agree to pay for one human Check, in USD.
MAX_PRICE = 1.25
# The deadline given to the human, from payment to answer. 24 hours.
CHECK_SLA_SECONDS = 86400
# Off unless you say so. With it off the fallback prices the Check and stops.
ORDERING = os.environ.get("COUNTERSIGNATORY_ORDER") == "1"


class Refund(TypedDict, total=False):
    refund_id: str
    customer_id: str
    amount: float
    reason: str
    decision: str
    status: str
    human_check: Dict[str, Any]


def approval(state: Refund) -> Refund:
    # Pauses the graph here. The value passed to Command(resume=...) comes back as the result.
    decision = interrupt(
        {
            "question": "Approve this refund? Type approve or reject.",
            "refund_id": state["refund_id"],
            "amount": state["amount"],
            "reason": state["reason"],
        }
    )
    return {"decision": decision}


def route(state: Refund) -> str:
    return {"approve": "send_refund", "reject": "rejected"}.get(state["decision"], "human_check")


def send_refund(state: Refund) -> Refund:
    # Your payment provider goes here. The example only prints.
    print(f"refund {state['refund_id']}: sent ${state['amount']} to customer {state['customer_id']}")
    return {"status": "refunded"}


def rejected(state: Refund) -> Refund:
    return {"status": "rejected"}


def human_check(state: Refund) -> Refund:
    # Nobody answered. The refund is not sent on this branch, whatever happens below.
    try:
        q = cs.quote(task="approval", tier="check", sla=CHECK_SLA_SECONDS, max_price=MAX_PRICE)
        check: Dict[str, Any] = {
            "market": q.market["id"],
            "price": q.unit_price,
            "currency": q.currency,
            "would_clear": q.would_clear,
            "quote_id": q.quote_id,
        }
        if not ORDERING:
            check["ordered"] = False
            check["note"] = "Set COUNTERSIGNATORY_ORDER=1 to place the order. Nothing was ordered or charged."
            return {"status": "held", "human_check": check}

        # Places the order and nothing more. order() never pays: a person opens
        # checkout_url, or an agent with a wallet pays at x402_pay_url.
        o = cs.order(
            market="check.general",
            template="approval",
            sla=CHECK_SLA_SECONDS,
            max_price=MAX_PRICE,
            input={
                "action": f"Send the refund of ${state['amount']} to customer {state['customer_id']}",
                "context": state["reason"],
            },
        )
        options = o.get("payment_options") or {}
        check.update(
            ordered=True,
            order_id=o["id"],
            order_status=o["status"],
            price=o["price"],
            pay_by=o.get("pay_by"),
            checkout_url=(options.get("card") or {}).get("checkout_url"),
            x402_pay_url=(options.get("x402") or {}).get("pay_url"),
            note="The order is unpaid. Pay at one of the two links before pay_by, then read the answer with cs.get_order(order_id).",
        )
        return {"status": "held", "human_check": check}
    except cs.CountersignatoryError as err:
        # A refusal or an outage must not turn into a sent refund.
        return {"status": "held", "human_check": {"ordered": False, "error": {"code": err.code, "message": str(err)}}}


builder = StateGraph(Refund)
builder.add_node("approval", approval)
builder.add_node("send_refund", send_refund)
builder.add_node("rejected", rejected)
builder.add_node("human_check", human_check)
builder.add_edge(START, "approval")
builder.add_conditional_edges("approval", route, ["send_refund", "rejected", "human_check"])
builder.add_edge("send_refund", END)
builder.add_edge("rejected", END)
builder.add_edge("human_check", END)
# interrupt() needs a checkpointer. Use a durable one outside a demo.
graph = builder.compile(checkpointer=InMemorySaver())


def ask(prompt: str, seconds: float) -> Optional[str]:
    """One line from the terminal, or None when the deadline passes first."""
    answers: "queue.Queue[str]" = queue.Queue()

    def read() -> None:
        try:
            answers.put(input(prompt))
        except EOFError:
            pass

    threading.Thread(target=read, daemon=True).start()
    try:
        return answers.get(timeout=seconds).strip().lower()
    except queue.Empty:
        return None


def main() -> None:
    config = {"configurable": {"thread_id": "rf_1001"}}
    graph.invoke(
        {
            "refund_id": "rf_1001",
            "customer_id": "1182",
            "amount": 40,
            "reason": "The item arrived broken. Policy allows refunds under $50.",
        },
        config,
    )

    # The graph is now paused on interrupt(). This is the app-side deadline.
    pending = graph.get_state(config).tasks[0].interrupts[0].value
    print(json.dumps(pending, indent=2))
    answer = ask(f"approve or reject, within {APPROVAL_TIMEOUT:g} seconds: ", APPROVAL_TIMEOUT)
    if answer not in ("approve", "reject"):
        print(f"\nNo approval within {APPROVAL_TIMEOUT:g} seconds.")
        answer = "timeout"

    final = graph.invoke(Command(resume=answer), config)
    print(json.dumps({k: final[k] for k in ("refund_id", "status", "human_check") if k in final}, indent=2))


if __name__ == "__main__":
    main()
