---
name: quote.read
version: 1
capability: quote.read
role: seller
protocol: town-mailbox.v1
summary: Answer quote requests with a priced quote, applying each request exactly once.
---
# Quote seller

Follow the town-protocol skill for mailbox mechanics. Your role rules:

1. On a quote_request, compute total_cents as quantity times
   unit_price_cents from the request body.
2. Record the request in your durable journal before replying, so a
   redelivered request is recognized and never applied twice.
3. Reply with a quote_response carrying the request id and total_cents,
   using a response identity derived from the request identity.
4. Acknowledge the request as processed, noting whether you applied it
   or recognized a duplicate.
