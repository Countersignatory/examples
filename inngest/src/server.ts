import express from "express";
import { serve } from "inngest/express";
import { inngest, refundApproval } from "./refund.js";

const app = express();
// Inngest sends function state in the request body, which can be large.
app.use(express.json({ limit: "4mb" }));
app.use("/api/inngest", serve({ client: inngest, functions: [refundApproval] }));

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => {
  console.log(`Inngest endpoint on http://localhost:${port}/api/inngest`);
  console.log(`Ordering is ${process.env.COUNTERSIGNATORY_ORDER === "1" ? "ON: the fallback places an unpaid order" : "OFF: the fallback prices the Check and stops"}.`);
});
