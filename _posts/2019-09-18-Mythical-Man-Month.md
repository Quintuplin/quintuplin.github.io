---
layout: post
title: "HW12: Mythical Man Month"
date: 2019-09-10
---

* <http://cs.cofc.edu/~bowring/classes/csis%20602/docs/The.Mythical.Man.Month.F.Brooks.pdf>
* <http://agilemanifesto.org/principles.html>
* <https://en.wikipedia.org/wiki/Agile_software_development>
* <https://www.cio.com/article/2385322/agile-development-why-agile-isn-t-working-bringing-common-sense-to-agile-principles.html>
* Textbook Ch 3

## Reflections on Mythical Man Month; and Why Agile is Unsustainable

### Mythical Man Month, response and analysis

MMM starts off with an extremely astute observation as to the shared humanity, joys, and woes of programming. It is the magic of creation, but like magic, it is specific in it's implementation lest you summon demons. It also finds itself frequently managed by others, and has layers of dependencies due to the fact that it is, in many ways, an apex field. What it speaks of, quite thoroughly at times, is the complexity and interconnectedness of the trade. But the title is about the "Man-Month", and the myth thus contained. The Man-Month is an optimistic time estimate. "How much can we get done in a month, and can we make it faster by adding more people?" The Man-Month has an answer, but that answer is rarely correct; there is always more than was predicted, no matter what the prediction was. And when something is behind schedule, management wants to throw more people at the problem; people who cause chaos; people who make the process even more complicated, and even more behind schedule. For complex projects, an increase in manpower intended to aid will instead harm, and greatly.

What is also questioned is the process of scheduling; programmers are optimistic, but results are statistic. The author finds that, no matter what the *intention* or *plan* was, half of total project time is spend testing and debugging. So, rather than 'falling behind schedule', they build it into their plans. They also assign a higher stretch of time to planning (double that of the time spent coding), because a well-planned project involves less wasted effort, and thus ends up being more successful, faster, once it's actually complete. Back to man-months, though, we now see the math behind a man-month-based disaster. For, when a project falls behind, and new individuals must be added; they cannot start immediately. They must be caught up, the project must be restructured, and all that time is still counting against the schedule. Only now it's a higher number of wasted hours, because it's compounded by the number of new people added. Moreover, this increase in manpower only leads to greater productivity when a project can be subdivided by the new number of individuals. If a project has two parts, then the third person is of little use. Their addition still adds complications, though, meaning that they are exclusively a drag on a project if not organized properly (which the addition of manpower mid-project would suggest is already the case).

In short, Brooks's Law holds true: "Adding manpower to a late software project makes it later." (pg 25)

Next, it questions team sizes; With the basic calculation (provided by the author and assumed to be true) that 1 good programmer is 10x faster than 1 mediocre one, it serves to reason that small teams of excellent programmers produce better projects faster; but the truth is, the numbers don't quite add up. A team of multiple 1000s might be unwieldy and less individually productive, but the team of 10 (the maximum optimal team size according to the author), even being 10x faster individually can still not match the giant-scale operation in terms of timely production. So, Mills's Proposal; the surgical team. Instead of 1 good small team, or a bunch of bad teams with good managers; why not turn it on it's head; make a moderate number of teams with one good lead each, and mediocre support staff? Each staff member would contribute to the team's productivity in a task-oriented manner, but in a way that enhances the productivity to the team lead, rather than detracting from it. What's particularly interesting in the modern day, however, is that each of the staff member's positions have been by-and-large made unnecessary. Many of the mechanics of programming, from automatic builds, to version control, to testing and logging environments which can be run a-la-carte; most of these positions no longer need to be handled by a human at a desk. The most significant position that still has meaning is that of the co-pilot; the sounding board who keeps track of the big picture and offers alternative ideas and looks behind the 'team lead'. Some of these roles are quite fastinating, but are hard to place in a modern context. Therefore, since large structural changes in the mechanics of programming necessitate a redesign of this team structure, I have a hard time envisioning what a modern equivalent would be, and thus am unsure how much I agree with this proposed team layout.

Finally (for this blog post, at least), in chapter 4 MMM falls to supporting and reflecting upon its conclusions leading to this point. After all, we have seen the layout for a team of 10 where only one individual in that team is actually programming; the elite makes all of the decisions and is the only one to be trusted. This assumption; that there is a vast and fundamental difference between the peak and the pleb; runs counter to my personal culture and has concerning ramifications. Not just for if the assumption is *true*, but even more so ramifications if the assumption is *believed to be true* independent of reality. But, in fact, the author does not reflect on this issue for long; they merely use it as a bridge to talk about the virtues of *conceptual integrity*, or "how much magically better something is when it's designed by only one person, or at least looks like it is". We're looking at an unironic positive interpretation of aristocracy here. Frankly, I find this to be a concerning world view, and one which can easily be misused to dismiss those whom are deemed 'below consideration'. The mediocre programmers of the world are, in their eyes, naught but chattel. When couched in such terms and implications, I find myself questioning all my previous agreements with the author of MMM, and wanting to safeguard myself against such personal ethical decay.

### The agile Manifesto, line-by-line

The agile manifesto is a ridiculous and horrifying document; as such, I will insult it below:

Their "highest priority is to satisfy the customer through early and continuous delivery of valuable software"; this means that the user gets to feel in real time how long it takes to complete the project, as they're sitting around using an incomplete project, and having plenty of time to get particular over details and start micromanaging.

They "welcome changing requirements, even late in development". In other words, Agile loves to scrap a project and start over, which is lucky because they'll probably do that a lot.

They "deliver working software frequently"; meaning that there is always a rush to deploy; which also implies not enough time to reflect or refactor.

They assert "business people and developers must work together daily"; this allows project parameters to change every day, which agile welcomes; developers, however, might find that they are unable to complete any goals because the goalposts keep being moved.

They "build projects around motivated individuals", which is business slang for "overtime is required to make up for our poor planning and time management"

They posit "the most efficient method of conveying information (...is...) face-to-face", which means that anything that could be a single sentence email must instead be a scheduled meeting; again, good luck getting work done.

"Working software is the primary measure of progress"; which means that if you have to work on an important feature that is challenging, but on the backend; don't bother. It won't look like progress, and you have a build due soon in which the business people will want to *see* progress.

"Agile processes promote sustainable development" is an outright lie, as nothing about this process is anything but soul-crushingly unsustainable.

"Continuous attention to technical excellence and good design enhances agility" translates to 'good programmers make better software'. Who could have guessed?

"Simplicity is essential" is a lovely mindset, but isn't actionable. A non-functional requirement, one might say.

"The best architectures emerge from self-organizing teams". Translation: your managers aren't going to help with organization or guidance; they're just here to make sure you give the business people whatever they ask for.

"At regular intervals, the team reflects on how to become more effective". What better item to cap off agile than *another pointless meeting*?
