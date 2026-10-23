---
layout: post
title: "Silly TCP Sender Idea: Buffer F*er"
date: 2026-10-15
---

Today's lecture used the image of a lightning bolt. First come the faint questing tendrils feeling out a path, then once one connects, the bright surge follows it. So I had a thought. What about a base station transmitter that behaves the same way?

## The lightning sender

1. Open a TCP connection with the usual SYN, SYN-ACK, ACK handshake, and use it to measure the round trip time (RTT).
2. Send a flood of segments numbered to *not quite* fill the bottleneck buffer, then send an RST to end the connection. The flood ignores ACKs and the congestion window and just dumps onto the network. The first bolt's size is a total blind guess at the buffer size. Later bolts can make a better guess from the last ACK they saw.
3. Wait. Accept ACKs, but don't respond to them or send any more data until a timer has cleared.
4. While still about two estimated RTTs before the predicted "buffer clear" time, send the SYN for the next connection. Once it's up, fire the next bolt. It might resend a few segments from the previous burst, based on the last ACK received, and again aims to nearly fill the buffer.

Why the RST? Each new connection has a chance of taking a different route. If routers along the way have full buffers too, a load-balanced network could put the next connection on whatever route is best at that moment. The previous bolt's path may no longer be the optimal one. Routers that spread load over equal-cost paths usually pick one by hashing the addresses and ports, so a new connection on a new source port can land on a different path.

## Why it doesn't hold up

On reflection it probably doesn't work.

- **A full buffer helps nobody, including you.** A buffer kept full is just queueing delay. Every packet behind it waits, your own included. That is bufferbloat.
- **A new route rarely dodges the bottleneck.** The bottleneck is most likely at the endpoint's access link, and every route has to pass through it. Load balancing happens in the middle of the network.
- **It doesn't scale.** Any one sender might get away with it, but it's bad for the health of the network as a whole. If everyone did it you'd get congestion collapse, which is the very problem TCP congestion control was built to prevent.

Still, I thought it was a fun idea, so I figured I'd share it.

## Design as intended and design in reality

The lightning demo in the lecture was a measurement tool. It checks that a link, especially a simulated one, really has the rate, latency and buffer size it was configured with. My idea just borrowed its shape for a different job.

What got me thinking was the boundary between design as intended and design in reality. In computer science we tend to treat implementations as axiomatic, and every successful individual operation ultimately has to be. But the implementation as written and the RFC design as proposed and agreed on make for some interesting contrasts. That's especially true in networking code, where built-in fault tolerance leaves particularly interesting wiggle room.

*Originally posted on my networking course's discussion board. Tidied up and expanded a little here.*
