---
name: vote.cast
version: 1
capability: vote.cast
role: voter
protocol: town-lab.v1
summary: Cast one signed ballot; a second ballot from you will be rejected.
---
# Voter

1. Register the vote.cast capability so the ballot box can find you.
2. On vote_open, send one signed ballot with your choice.
3. One agent, one vote: the ballot box counts your first ballot and
   rejects any later one from the same identity.
4. Keep the broadcast result for your own records.
