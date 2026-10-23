---
layout: post
title: "TDD and Greedy Pathing"
date: 2026-10-14
---

I've been thinking more about the greedy algorithm question from last lecture. I overstated my position a bit in class, so this is the more considered version.

## TDD as a search

The definition of test driven development we used goes like this. Choose the smallest possible failing test that moves towards the requirements. Then make the smallest possible change that passes it. Repeat.

That feels like gradient descent, or a pathing algorithm. It is a greedy one, though, and not necessarily the most efficient kind.

- **Gradient descent.** When training a neural net you generally want large steps early on, then smaller ones once you start closing in on a minimum. You might also start from several random points and take a stochastic approach. That is roughly where the analogy falls apart, since TDD always takes the smallest step from wherever it is.
- **Routing.** Algorithms like A\* or Dijkstra's need a fixed graph of nodes, which we don't really have. Unless we map the classes out first. Or build a k-nearest-neighbour graph of semantic similarity, placing properties in an n-dimensional space and grouping the ones that sit close together.

A few classes back there was an idea that if you map out which functions are used where, you can redraw the class boundaries to match. That almost argues for writing raw, pure, generic functions first and recombining them into classes afterwards. The usual order starts with the class definition and puts in "what makes sense".

Whatever the philosophy, pathing and model training share the same goal. They optimise towards a hopefully global minimum. For software that's the point where it meets the requirements well enough and fails rarely enough.

So how far could this be pushed? What other approaches could keep TDD as a base but change the specifics?

## Where the gap is

Test case prioritisation is already a well-studied area. It takes a suite of tests that already exist and decides which to run first, using things like coverage, past failures, cost or risk. [Rothermel et al. (2001)](https://doi.org/10.1109/32.962562) is a classic starting point, and [Mukherjee and Patnaik (2021)](https://doi.org/10.1016/j.jksuci.2018.09.005) survey the many approaches since.

TDD's problem is different. When you pick the next test, it doesn't exist yet. All you have is a list of candidate behaviours, the test list Kent Beck describes in *Test-Driven Development: By Example*. How to build that list, and which item to take next, has much less formal method behind it. That looks like a real research gap, and one worth some preliminary trials to see how they pan out.

## Aesthetics

Something else has been bugging me. Clean code and code smells are excellent principles, but many of them don't come with a measurable metric. I've come to think this course is really about aesthetics.

Think about learning to paint from the Renaissance masters. There was a certain amount of geometry, but much more was pure artistry: exhaustive effort, honing the craft over time and chasing aesthetic perfection. That quality is somehow subjective and universally recognisable at the same time.

Empirical studies and quantified tests of more algorithmic approaches should lead to standardised, scalable coding practices. I have a lot of confidence in that, and those practices will probably hold up better in the era of AI, which has no sense of beauty. But the sense of aesthetics is at risk of being lost along the way. I think that is one of the central conflicts of the current era in technology and computer science as a whole.

Anyway, just a wild thought.

*Originally posted on my software engineering course's discussion board. Tidied up and expanded a little here.*
