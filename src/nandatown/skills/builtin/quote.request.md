---
name: quote.request
version: 1
capability: quote.request
role: buyer
protocol: town-mailbox.v1
summary: Discover a seller, request a quote, and validate the total yourself.
---
# Quote buyer

Follow the town-protocol skill for mailbox mechanics. Your role rules:

1. Find a participant whose capabilities include quote.read.
2. Send a quote_request with the sku, quantity, and unit price from
   your task, under a message identity you keep stable across retries.
3. Claim the quote_response from your inbox and check the total
   yourself: quantity times unit price. Never trust transport success
   as task success.
4. Acknowledge the response as processed with a note stating whether
   the total was correct and what you expected. Your note is your
   attributed assertion in the run's evidence.
