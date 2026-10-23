---
layout: post
title: "Dynamic TCP: In-Flight Header Modification"
date: 2026-10-08
---

I was double checking my understanding of TCP headers and got to thinking about arbitrary extensions.

## The idea

TCP headers aren't encrypted, but they are checksummed. The checksum is only checked at the receiver. So headers travel unmodified by convention, and nothing along the path actually enforces it.

A TCP header can carry up to 40 bytes of options on top of its 20 fixed bytes. If a sender uses all of that space for its own options, so be it. But if an intermediate router sees spare space, it could add extra option "riders" of its own, provided a second router further along strips them away again before delivery.

Options are self-describing (a kind, a length, then the value), and a couple of kind numbers are even set aside for experiments. So riders could be numbered so they never collide with the sender's real options, and recognised and stripped before delivery. They are size limited, of course.

A VPN wraps the original packet, TCP header and all, inside its own headers. That still doesn't stop riders being added on intermediate hops. They would just need clearing out before the VPN endpoint unwraps the packet, which may or may not be the same place as the client.

If that works, a set of routers running the same extension could use that option space freely, and invisibly from the client's point of view. They could pass information that lets an ordinary TCP connection follow dynamic, mid-path custom rules. They could augment path traces too, even on HTTPS connections (TLS encrypts the payload, but the TCP header stays in the clear) and across networks that don't answer traceroute. All you need is to control the routers.

There isn't much capacity, but every dynamic router you add makes the connection a little more dynamic. And that's before getting into shenanigans like recomputing the checksum, which might remove the need to strip the riders at all. You would simply trust the endpoint to ignore fields it doesn't recognise.

## What actually holds

It turns out the real picture is both stricter and much looser than this.

**Stricter in principle.** A router is a network layer device. By the end-to-end principle it should read and write the IP header only, and from its point of view the TCP header is just payload. The one header routers always change is the IP header, since every hop decrements the TTL (the hop limit in IPv6). Precision matters here too. The IP packet and header are one thing. The TCP segment and header travel inside the IP payload.

**Looser in practice.** Plenty of equipment touches TCP segments anyway, and not just firewalls. The everyday example is segmentation offload. A sending network card can take one huge chunk of data from the CPU and cut it into segments that fit the path, writing a fresh header for each. A receiving card can wait a moment and merge back-to-back segments from the same flow into one large segment, so the CPU makes one routing decision instead of several. A Linux box forwarding between two network cards can do both, so the segment boundaries that leave it often differ from the ones that arrived. Capture the same transfer at both ends and you can see it. Some satellite links go further and rewrite the advertised window in ACKs to slow down a sender that would otherwise overload the link.

So in-flight changes don't need stripping at all, as long as what comes out is valid TCP. Receivers are required to ignore options they don't implement ([RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html), requirement MUST-6). The accurate summary is "no holds barred, as long as the payload bytes arrive in the end".

**Sequence numbers survive the shredding.** My follow-up worry was about ACKs. If a sender sends bytes 2001 to 3000 as one segment, and something mid-path splits it and half goes missing, could the receiver end up acknowledging only part of it? It can, and nothing breaks. SEQ and ACK numbers count bytes in the stream, not segments. Splitting or merging segments writes new SEQ values into the new headers, but the byte numbering itself never changes. The receiver just acknowledges up to the last byte it has in order, and the sender resends from there.

**Header tricks are fragile on paths you don't control.** Honda et al. measured exactly this kind of thing on real Internet paths in [*Is it Still Possible to Extend TCP?*](https://www.cl.cam.ac.uk/teaching/2021/CompNet/files/honda2011still.pdf) (ACM IMC 2011). Middleboxes on some paths strip unknown options, some rewrite sequence numbers, and resegmentation by offload breaks anything that assumes segment boundaries. Riders would work across routers you own and fail unpredictably anywhere else. Even deliberate tricks like throttling a sender by rewriting its advertised window aren't something routers do out of the box. ECN, the standard way for routers to signal congestion without dropping packets, often isn't supported or switched on in routers.

**QUIC changes the landscape.** QUIC is now a large share of traffic. It runs over UDP and lives in user space, so the operating system still only sees TCP and UDP at the transport layer. It fixes TCP's head-of-line blocking, where one missing packet holds every later byte in the receive buffer. It also encrypts nearly all of its own header, partly so middleboxes can't do this kind of fiddling. That leaves TCP shenanigans looking less useful for future-facing work.

## Why bother

These aren't the ways the techniques are meant to be used, only ways they technically could be. Looking for weird edge cases like this teaches a lot about how something normally works, and also about how it actually works. Every so often it might turn up something new in the process.

*Originally posted on my networking course's discussion board. Tidied up and expanded a little here.*
