---
layout: post
title: "HW7: Reflections"
date: 2019-09-05
---

* <https://en.wikipedia.org/wiki/The_Magical_Number_Seven,_Plus_or_Minus_Two>
* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/rfid-tire-pressure-2010-002-tpms.pdf>
* <https://www.markey.senate.gov/imo/media/doc/SPY%20Car%20legislation.pdf>
* <http://www.agiledata.org/essays/tdd.html>
* Textbook Ch 4

### Reflections on Test Driven Development: 

*Seven, +-2* covers some of the realities of human limitation. It's core argument is that, given n stimuli, an average human will lose track after 7. This is the limitation of the human brain, and in my understanding seems roughly similar to the register-based storage within a CPU. Our working memory. Meanwhile, our memory span is the net capacity; the human brain can hold in each of these 'slots' a single concept. Note that since our brain works by reference and analogy, our internal 'bits' are concepts, emotions, or otherwise termed single elements. The most equivalent entry in a computer is described as a 'bit', but by my interpretation it seems more analogous to a 'word'.  

What this means for TDD? Well, if humans are so limited (and they most definitely are), then we will be significantly hampered when trying to debug or test code which does more than 7 things. In other words, any large project. *In the zone* or not, a developer is human, and simply cannot look at a large program project structure and see how everything impacts everything else, and where an error might be. Test driven development means that instead of trying to look back at old code and immediately become overwhelmed with 'more than 7' changes, we can instead write tests one-at-a-time while we still understand what the code does and is supposed to do. After all, we have limitations, but our tests are only limited by ourselves.

*The Tire Monitoring System* paper, meanwhile, shows that the State Mandated TPMS has a glaring security issue; it broadcasts the tire pressures within a vehicle wirelessly, and with a unique identifier; making any vehicle able to be tracked by simply scanning for signals and tracking where that unique ID is sensable from. While it is range-limited, this leads to the inveitable possiblity of simply installing tracking sensors at common intersections; effectively tracing all movement of the vehicle (and thus, likely, the owner). The further tests and experiments show both that the system is significantly flawed and needs to be fixed; but some fixes can be recommended and solved with more development. 

As a form of response, a *bill* was proposed to ensure cybersecurity requirements be enacted to protect the population from non-secure cars. These requirements include allowing users to disable trackable activities without loss of functionality, as well as requesting.  

What this has to do with test driven development?  

Well, TDD is the process by which code is written, tested, modified, tested, modified, tested, etc etc. What it is most useful for is maintining functionality after feature changes or refactoring; since the tests are already set-up, one can easily re-run them all and ensure that all old functions still work as intended. When new funtionality is set up, new tests are also added to ensure that new functionality is performing as intended. The strentchs of TDD is that code will be excellent at achieving the envisioned goals and issues, and will be reliable over versioning. However, the weakness of TDD is that it does nothing to ensure that any unexpected or forgotten flaws be detected and fixed; after all, if all the tests pass, the assumption is that the code works. If the test fails to account for a combination of events that end up being significant, then the developers will erroneously believe their code is perfect and possibly fail to address the issue in time. One might assume, therefore, that the Tire Monitoring System has fallen to such a pitfall; they envisioned the issues of a wired system, came up with a wireless one, tested that it could tell the car computer the tire pressures, and once it passed the tests, called it complete. However, since they forgot about security (or at very least put very little time and effort into security), their tests were insufficient and a significant issue arose after deployment. However, I can hardly blame this on TDD - this is merely a guess. It is extremely frequent in nearly all development environments that security is overlooked, forgotten, or otherwise not prioritized. In addition, a testing environment is static and by definition predictable; compared the active chaos of having real humans pen-testing one's systems.  

Ultimately, Tests are the best way to determine that the code is functioning as intended. But one can still simply miss important elements of the design; a test you forget to make is a feature or contingency your software cannot be trusted to handle correctly.
