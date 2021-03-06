---
layout: post
title: "HW9: Reflections"
date: 2019-09-10
---

* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/RapidDevelopmentChapter7.pdf>
* <https://hub.packtpub.com/11-predictions-for-the-future-of-programming/>
* Textbook Ch 2

### Reflections on the Future of Programming

With automatable testing and deployment, elements from the iterative design process will only become more prevalent. Meanwhile, with the significant majority of softwares having some form of access to the internet, updates and evolving scopes over time necessitates a software model which allows for future development and long-term support; but also for quick fixes whenever needed.  

This suggests a future of an extensive and test-heavy auto-deployment process; The software will have evolving goals that each must be organized, designed, and completed. Miniature cycles of waterfall, to ensure that long-term-design parameters are fulfilled, but short duration and limited scope, so that features can be added as-ready rather than all-at-once. As a programmer, you work on a new feature or process for your particular sprint, then attempt to deploy it; the automated test/deploy system handles the rest, and you find out if you're going to be bugfixing or moving on to the next thing.

This sort of process also necessitates a refactor process; this can either be a refactor cycle which repeats every **n** new-feature cycles, or a continuous process by a discrete team. At any rate, excessive attention must be made for software to follow *interface* rules, as this allows software portions to be rewritten or refactored without breaking the various dependents (espectially those in unexpected areas). In a similar fashion, if one adds a new feature that calls an existing interface, and the existing interface has a bug, it is important to fix the old module rather than create code which relies on the module breaking 'predictably'; doing so means that one's own code is almost guaranteed to stop working the moment refactors get around to fixing the erroneous core.

Documentation and planning between sprints with this layout is absolutely essential; if only to keep track of which features have *already been made*. Modules being called in multiple conditions and situations is great for efficiency of code, but only if a developer doesn't accidentally keep creating new ones with minor (or no) differences to existing ones. Well-designed and easily-parsed documentation combined with a modular design style for each module is essential, then, so that a developer can quickly discern what they need to write, and what they can utilized from the existing code-base.

This setup is very similar to the evolutionary-delivery model, but with some core distinctions. Utmost is the complete lack of a final version; software being 'complete' is by and large a thing of the past - and arguably was an unrealistic concept even then. 

Meanwhile, the code should also utilize exiting frameworks whenever possible. The more quickly and effectively the computer science community can settle on standards and unify frameworks, the better. We don't need to be replicating work decades-old on an individual scale; we need to be using something that will grow with us. The greater level of integration of shared tools the programming community can reach, the more capable we will be (and our softwares will be) to evolve and continue to remain relevant as hardwares, softwares, and protocols evolve; those frameworks themselves can integrate the best of the new, retain compatiblity with the old; and softwares can make minimal changes in order to incorporate the consolidated improvements of constant development in places where the individual developer has neither the time nor resources do improve themselves.  

Shared frameworks like Pandas, SQL, Docker, etc create a unified programming environment that constantly improves and allows code that imports/utilizes them to benefit in the shared progress. A greater emphasis on utilization of these tools in the future (and greater development of more/better tools) is an inevitability; and a very good one. While one must take care to utilize them correctly, software can only be improved by utilizing the best tools available; this approach is only going to become more true as computer utilization completely supplants traditional hard-copied styles of beaurocracy and documentation, and places greater focus on a small number of well-honed modular frameworks, rather than an infinite collection of distinct bespoke systems.
