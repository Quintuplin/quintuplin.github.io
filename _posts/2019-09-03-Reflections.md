---
layout: post
title: "HW5: Reflections"
date: 2019-09-03
---

* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/Therac25Accidents.html>
* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/The%20Radiation%20Boom%20-%20After%20Stroke%20Scans,%20Patients%20Face%20Serious%20Health%20Risks%20-%20NYTimes.com.pdf>
* <https://www.ic3.gov/media/2016/160317.aspx>
* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/levesonSoftwareAccidentsSpacecraft.pdf>
* <http://cs.cofc.edu/~bowring/classes/csci%20362/docs/SpectrumFBIcaseFileSytem.pdf>
* <http://www.washingtonpost.com/wp-dyn/content/article/2010/10/20/AR2010102006754.html?noredirect=on>
* <https://www.pcmag.com/news/301010/years-late-and-millions-over-budget-fbis-sentinel-finally>
* <https://spectrum.ieee.org/riskfactor/computing/it/fbis-500-million-sentinel-case-management-system-still-has-major-operational-kinks-ig-reports>
* <https://www.entrepreneur.com/article/329019>
* Textbook Ch 13, 14

### A Response to Why Software Fails, and What Happens when it Does:

These articles offer devastating insights into how and why major projects fail. From the FBI's 'Virtual Case File', which was an absolute garbage fire, to it's still deeply flawed successor 'Sentinel', to a series of NASA projects which all failed due to similar organizational or programmatic mistakes, these articles tell a tale with one clear moral. Big projects cannot be entrusted to the 'agile' development process.  

Well, perhaps that's an overstatement. After all, there is a lot more to unpack here than simply blaming it on starting a project with no clear goals and no clear goalposts to track progress towards them. The NASA projects had, apparently, nobody testing or overseeing the code; they allowed the hardware developers to create their own software at times without properly testing that they would work well together in a complete whole, reused old code for new purposes without refactoring or even (apparently) considering if the code was suited or designed for such tasks, and allowed such things as a software failure state which **shut down the machine** when an unexpected input was recieved; an error which, predictably, caused core systems to shut down mid-flight and jeapordized the mission. If the NASA projects could be summarized under a blanket statement, it would be that the physicists and engineers had little to no respect for the software that would run their machines; and they paid the price with failure.  

Meanwhile, in FBI-land, project management was the primary issue. When they started to design their new system, they didn't start with a project structure, clearly defined requirements, and consultation from database experts. They put a resident tinkerer in charge and he was happy to figure it out as they went. Such a process is fine for a small script like he had been developing until now, but was utterly insufficient for the massive task of redesigning and reorganizing the digital paperwork of an entire global spy network. So, while they saved time by 'starting immediately', they ultimately lost half a decade and half a billion to create a system that was outdated the day it was released.  

Another core failing of the VCF/Sentinel design process was how ongoing and micromanaged it proved to be. The FBI outsourced the programming, but instead of giving clear, consice requirements and letting the developers develop, they created (and constantly expanded upon) a near-800 page monolith of excessively specific designs. They engaged in a development cycle that involved so much micromanagement of insignificant details that the development process devolved into reactionary listening to orders. One can only assume that, under such conditions, any programmer would lose their spirit and simply do what the latest document says; independent of how poorly planned, redundant, unnecessary, or flat-out backwards the 'new requirements' would be. When the goalposts move so constantly, it becomes impossible to progress; one simply constantly plays catchup to ideas and decisions that when thought about too hard clearly aren't leading anywhere, and especially aren't leading to a project's completion. And when you're a contractor and you're getting paid to do what they say, and when they wouldn't listen anyways, why fight it?  

The outcome to a lack of project management is not a bad product... it's no product. These examples are extreme, but very real; software projects fail all the time due to issues like these. It doesn't come down to having the best programmers, an unlimited budget, or even unlimited time. If you aren't organized sufficiently for the scope of the project, you won't succeed.
