<div align="center">

<img src="./ascii.svg" width="760" alt="happinessisreal: an ASCII Pikachu, typed out line by line"/>

<img src="./stats.svg" width="620" alt="Contributions in the last year"/>

[github](https://github.com/happinessisreal) &nbsp;·&nbsp;
[projects](#projects) &nbsp;·&nbsp;
[stats](#stats)

</div>

<img src="./hd-about.svg" width="620" alt="about"/>

> I build across the whole stack: compilers, optimisation services,<br>
> ML dashboards, 3D web and mobile apps.

I'm drawn to two things in particular: tools that speak **Bangla**, and systems<br>
where **math keeps the AI honest**. Most of what's below was built for a class,<br>
a hackathon or a friend, then polished until it was worth showing.

<img src="./hd-projects.svg" width="620" alt="projects"/>
<a id="projects"></a>

<img src="assets/logos/alveelan.svg" width="18" align="top"/> **[alveelan](https://github.com/happinessisreal/alveelan)** &nbsp;·&nbsp; <samp>rust, llvm</samp><br>
A programming language for kids, written in Bangla. Bangla keywords, Bangla<br>
digits and Bangla error messages, compiled to native code through LLVM.

<img src="assets/logos/gridwise.svg" width="18" align="top"/> **[gridwise](https://github.com/happinessisreal/gridwise-energy-optimizer)** &nbsp;·&nbsp; <samp>python, fastapi, scipy</samp><br>
An LLM turns operator notes into typed constraints, then an exact linear<br>
program finds the cheapest 24-hour energy plan. Built for BUP CSE Fest 2026.

<img src="assets/logos/dhaka-aqi.svg" width="18" align="top"/> **[dhaka-aqi-dashboard](https://github.com/happinessisreal/dhaka-aqi-dashboard)** &nbsp;·&nbsp; <samp>flask, scikit-learn</samp><br>
Air-quality monitoring and next-hour PM2.5 forecasting for Dhaka,<br>
on OpenAQ data, with a live dashboard.

<img src="assets/logos/doofen.png" width="18" align="top"/> **[doofen](https://github.com/happinessisreal/doofen)** &nbsp;·&nbsp; <samp>astro, react three fiber</samp><br>
A scroll-driven 3D agency site. A wireframe building assembles as you<br>
scroll, and a built-in CMS manages the portfolio.

<img src="assets/logos/scormplayer.svg" width="18" align="top"/> **[scormplayer](https://github.com/happinessisreal/scormplayer)** &nbsp;·&nbsp; <samp>javascript, vite</samp><br>
A test harness for e-learning packages. It validates them against the ADL<br>
schemas and logs every LMS API call live.

<img src="assets/logos/bup-diary.svg" width="18" align="top"/> **[bup-diary](https://github.com/happinessisreal/bup-diary)** &nbsp;·&nbsp; <samp>flutter, supabase, gemini</samp><br>
An AI journal you can talk to. It finds your most relevant past entry<br>
before it answers.

<img src="assets/logos/expense-tracker.svg" width="18" align="top"/> **[swing-expense-tracker](https://github.com/happinessisreal/swing-expense-tracker)** &nbsp;·&nbsp; <samp>java, swing</samp><br>
A desktop finance tracker with charts and salted-hash accounts.

<img src="assets/logos/habit-tracker.svg" width="18" align="top"/> **[Goriber-Habit-Tracker](https://github.com/happinessisreal/Goriber-Habit-Tracker)** &nbsp;·&nbsp; <samp>c11</samp><br>
A terminal study tracker with no dependencies: pomodoro, streaks and stats.

<details>
<summary>the logos are philosophy jokes</summary>
<br>

<samp>gridwise</samp>: the best of all possible grids, a bolt striking the one optimal<br>
vertex of the feasible polytope (Leibniz, via Voltaire).<br>
<samp>alveelan</samp>: "এটি অ নয়", this is not অ (Magritte).<br>
<samp>dhaka-aqi</samp>: an ouroboros. The recursive forecast feeds on its own predictions.<br>
<samp>scormplayer</samp>: the play button is a Penrose triangle, like full SCORM compliance.<br>
<samp>bup-diary</samp>: The False Mirror, a diary that looks back.<br>
<samp>expense-tracker</samp>: Zeno's budget. Spend half of what's left, forever.<br>
<samp>habit-tracker</samp>: one must imagine Sisyphus happy.

</details>

<img src="./hd-stack.svg" width="620" alt="stack"/>

<samp>python &nbsp; rust &nbsp; typescript &nbsp; dart &nbsp; java &nbsp; c &nbsp; fastapi &nbsp; flask &nbsp; scikit-learn &nbsp; llvm &nbsp; astro &nbsp; three.js &nbsp; flutter &nbsp; supabase &nbsp; docker</samp>

<img src="./hd-stats.svg" width="620" alt="stats"/>
<a id="stats"></a>

<div align="center">

<img src="./streak.svg" width="620" alt="Current and longest streak"/>

<img src="./langs.svg" width="620" alt="Top languages by bytes and by repo"/>

<img src="./year.svg" width="620" alt="The last year, one character per day"/>

</div>

<img src="./hd-about-this-page.svg" width="620" alt="about this page"/>

Every graphic here is generated in this repository. None of it is embedded<br>
from anyone else's server, so nothing here can rate-limit or go dark.

`ascii.svg` is the whole picture turned into characters by<br>
[`scripts/make_portrait.py`](scripts/make_portrait.py). Each character's density follows brightness,<br>
and its colour is one of ten k-means clusters of the image. That gives every region<br>
one deliberate colour instead of per-character noise.

The stats and these section headings are drawn by [a scheduled action](.github/workflows/stats.yml)<br>
from the GitHub GraphQL API once a day, and it commits only what changed. The day<br>
window is pinned to whole UTC days and only public repositories are counted,<br>
so the output is identical no matter who runs it.

The graphics animate with SMIL inside the SVG, because GitHub strips scripts<br>
and CSS from READMEs. For the same reason, the typeface is [JetBrains Mono](scripts/fonts),<br>
subset and inlined as base64 in every file.<br>
<samp>year.svg</samp> uses the portrait's character ramp, quiet to loud: <samp>· : + # @</samp>
