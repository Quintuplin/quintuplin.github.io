---
layout: post
title: "Goofy Buffer Protocol Idea: Round Robin Favoritism"
date: 2026-10-22
---

I was thinking about the router buffer management schemes from lecture and had an idea for one. It might be good. It might be terrible.

## The rules

- When packets arrive at an empty buffer, the first sender is greenlit into it. That sender becomes the *chosen sender*.
  - The chosen sender's packets fill the buffer until it is full.
  - No other sender's packets are allowed into the buffer.
  - Once the buffer is full, it locks.
- The router then interleaves one FIFO and one FILO (first in, last out) slot until the buffer is empty.
  - The FIFO slot drains the buffer in order, so the chosen sender gets a whole burst through.
  - The FILO slot serves everyone else, newest packet first. Each of their packets has a random chance to be passed on quickly or dropped completely.
- Once the buffer is empty, the next incoming packet from anyone except the previous chosen sender picks the new chosen sender.
  - The cycle repeats.

## What it does

- **Someone always finishes.** Every dropped packet has to be resent. Dropping packets from every sender means every sender resends, which means more congestion. Picking a chosen sender guarantees that at least one sender comes off the resend list each cycle.
- **There's no safe traffic to throw away.** You can't just drop UDP to protect TCP, because QUIC runs over UDP and does its own resending, much like TCP. So deep packet inspection to sort traffic by type buys very little.
- **Mice sneak through.** Short flows can get through in the FILO slot, and even heavy hitters make a little progress at random.
- **One sender per cycle makes real progress.** The favoured source gets fast, meaningful throughput with no packets dropped.

## Extension: an actual round robin

Why call it round robin if it doesn't round robin? Make a set of M buffers, each working like this: one source at a time, buffer filled, locked, emptied, rotated. That gives a true round robin with a longer rotation list. Keep the FILO slot mixed in, so random packets from senders outside the current M still get passed on with no queueing delay. Keep the total buffer size and the number of buffers small, so it doesn't drift into bufferbloat.

This starts to resemble [fq_codel](https://www.rfc-editor.org/rfc/rfc8290.html), which keeps a queue per flow, serves the queues in a round robin and lets new, sparse flows go first so mice skip the queue. The twist here is the locking. A buffer belongs to one sender until it drains.

## Flaws, counter-flaws and counter-counter-flaws

**Critical flaw.** Chain two round robin favoritism routers together and they may pick different favourites. Router B then throws away almost all of router A's carefully buffered burst, apart from the few packets that win the random draw, and the odds of those being in order are low.

**Another flaw.** It relies on greedy senders. A sender that doesn't keep sending will never fill its per-sender buffer, so a real version would need a timeout to stop a slow chosen sender holding the buffer open.

**Counter-flaw.** A chain of routers running the same scheme could pass a "current favourite" flag downstream, so the next router prioritises the same sender in one of its M buffers. That brings back traffic prioritisation without deep packet inspection. DiffServ does something similar with a class marking in the IP header ([RFC 2474](https://www.rfc-editor.org/rfc/rfc2474.html)).

**Counter-counter-flaw.** Impostor routers claiming their traffic is favoured would be a problem. DiffServ has the same weakness, which is why networks tend to reset or ignore markings that arrive from outside their own trust boundary.

Thoughts?

*Originally posted on my networking course's discussion board. Tidied up and expanded a little here.*
