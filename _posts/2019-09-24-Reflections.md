---
layout: post
title: "HW14: Testing Reflections"
date: 2019-09-24
---

* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/software.testing.introduction.pdf>
* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/rep_and_analy.pdf>
* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/MutationTesting.pdf>

If the files timeout when trying to open them, try this handy linux command:

```wget --retry-connrefused --waitretry=1 --read-timeout=20 --timeout=15 -t 0 "http://cs.cofc.edu/~bowring/classes/csci%20362/docs/software.testing.introduction.pdf"```

##  Reflect on the Readings about Testing

The primary doc starts with a very intimidating quote: "Testing consumes at least half of the labor expended to produce a working program"

However, while it goes in-depth into how disliked testing is, I think that such attitudes are primarily an artifact of time management, rather than one of testing itself being a miserable activity. After all, in an ideal world, your test environment provides more than nothing; it provides validation, and peace-of-mind. But coming back to that time management issue; when someone is simply ready for a project to 'be done', then anything that delays the deployment of code that is 'mostly finished' is the enemy. When testing finds no issues, it was a waste of time; when it finds issues, it's a criticism of the quality of the work, as well as the enemy which creates more work. When viewed from such a perspective, who would ever want to test their code? And who might simply hope that their code is good enough to not need it?

But they do run into errors; many of which are found much more efficiently when tested correctly, rather than cropping up in the 11th hour. So it's worth it to do it right.

One of the most fantastic of test-setups is, in my opinion, one where the tests are made first. After all, what is a clearer indication of progress than pressing a 'test' button and getting more green checks than the last time you ran it? What a magical experience coding could be if you knew, not only exactly what every function was going to be and do, but also that with barely a second expended you could know with reasonable certainty if that segment of the code was done; production ready; finally finished! Unfortunately, such a setup requires extensive planning and pre-documentation for such wonderful tests to be able to even exist; and even more time to create them all. Alas, if only every project could *have already been designed by a world-class software engineer* and we could just code without worry. But we're the engineers here, and not every project has a client who is capable of making waterfall possible. So we're forced to make do.

Phases of a Tester's Mental Life (paraphrased):  
* Phase 0: Utilize Testing to support debugging only
* Phase 1: Testing to prove code works
* Phase 2: Testing to prove code doesn't work
* Phase 3: Testing to manage the percentage of working/not working
* Phase 4: Testing as a way of life; Coding to make testing of the code simpler and more effective, with testing itself as the end goal.

The phases in a tester's mental life is an interesting segment; it mostly denotes a hierarchy of testing, where phase 0 is a programming grunt who has no understanding of what tests are nor should be, and phase 4 is one who has transcended mere tests and become a being of pure intellect. Clearly you want to be in phase 4... right? But these phases have a lot of details and curiosities even within them. Many of these phases have, for instance, evolved over real-world decades of industry experimentation; as such, they represent more than just the author's opinion (probably). Meaningful insights such as this cutting remark against phase 1 - testing to show software works: "it is self corrupting. It only takes one failed test to show the software doesn't work, but even an infinite number of tests won't prove that it does" (p. 5). It goes further, by saying that even though the later phases may be more advanced, they're all cumulative; they're all valid.

*Representation and Analysis* also talks about testing, but from a different perspective; such as how to make better graphs of logic in order to make tests which account for every state and state changes; this uses the graph-theory layout of a program to better understand where tests need to be. This is very similar to a mathematical approach, as each state and state change can be attempted to be 'proven' once they're clearly broken down in this manner.

*Mutation in Testing*, finally, looks into testing test algorithms themselves; how should it be done? They compared mutant code (code that has been semi-randomly altered to introduce errors), real faults (code with known errors), and hand-seeded faults (manually added errors) in order to determine which method, if any, is most effective and where the field should evolve when generating new testing frameworks? After all, feeding a framework the best possible data is necessary for getting the best possible framework (not so dissimilar to how a learning machine might require good data; and not necessarily avoiding using a learning machine, either). Their results were, unsurprisingly, that faults are hard to find in a generalist testing environment; most tests will need to be hand-seeded on an individual test basis to have much utility or validity. This has the implication that testing will likely not have a universal "test software" that can simply be bought and ran on any given code; tests must be hand-written on a per-project basis. The downside is that anyone who hates tests will likely never get away from them. The upside, though, is that testing is likely to continue to be a valid specialization. So that's nice, I think.
