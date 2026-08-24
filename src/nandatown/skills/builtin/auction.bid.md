---
name: auction.bid
version: 1
capability: auction.bid
role: bidder
protocol: town-lab.v1
summary: Bid your valuation in a sealed auction, pay only if you win.
---
# Auction bidder

1. Register the auction.bid capability so auctioneers can find you.
2. On auction_open, submit one signed bid at your valuation before the
   close. Bids after the close will be rejected; do not resubmit.
3. If you receive auction_won, pay exactly the winning amount to the
   auctioneer and report the payment.
4. If you lose, you pay nothing. Record the result you were sent.
