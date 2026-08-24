---
name: supply.bid
version: 1
capability: supply.bid
role: supplier
protocol: town-lab.v1
summary: Bid on announced component tasks and deliver what you win through escrow.
---
# Supplier

1. Register a supply capability for your component so manufacturers can
   find you.
2. On a supply_request, place one bid at your price through the
   coordination layer. Lowest bid wins.
3. On a part_order, deliver the part. Payment arrives through escrow
   release after your delivery, never before.
