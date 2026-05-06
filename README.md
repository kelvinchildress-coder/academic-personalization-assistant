\# Academic Personalization Assistant

Coach-set personalized XP goals on top of TimeBack data, with daily-recalculating targets,  
trend tracking, and Slack reports. Built for Texas Sports Academy (TSA), Calendar A,  
SY 2025–26.

\#\# Status

> **Last completed checkpoint:** 1 — stale roster cleared (`students.json`/`student_ids.json` reset), `requirements.txt` extended for scheduling/Slack/PyGithub.

If a chat session dies mid-build, a fresh chat can resume by reading this checkpoint  
marker, the file tree, and the recent commit messages.

\#\# Architecture (Path B — laptop scraper \+ GitHub Actions for always-on services)

\#\# Slack delivery model

Reports post to the \`\#sports\` channel as a thread:

\- \*\*Parent message\*\* — header (e.g. \`\*Morning Report — Mon May 11\*\`)  
\- \*\*Threaded replies\*\* — one per coach, tagging the coach with \`\<@U…\>\` and listing  
  their students with today's target, pace, and accuracy. Coaches resolved at runtime  
  by the bot via \`users.list\`; no hand-collected user IDs in the repo.  
\- \*\*Supervisor digest\*\* — one threaded reply at the end tagging Kelvin Childress with  
  the campus-wide standout issues and successes.

\#\# Roster

Texas Sports Academy, \~35 students. Coaches:

| Display name        | Role        |  
|---------------------|-------------|  
| Amir Lewis          | Coach       |  
| Cait Arzu           | Coach       |  
| DJ Tripoli          | Coach       |  
| Ella Alexander      | Coach       |  
| Graham Spraker      | Coach       |  
| Greg Annan          | Coach       |  
| Lisa C Willis       | Coach       |  
| Kelvin Childress    | Supervisor  |

\#\# XP target rules (locked)

| Subject      | Daily XP | Notes                                    |  
|--------------|---------:|------------------------------------------|  
| Math         |       25 | Base rate                                |  
| Reading      |       25 | Base rate                                |  
| Language     |       25 | Base rate                                |  
| Writing      |     12.5 | Flat (TimeBack averages alt-week 25\)     |  
| Science      |     12.5 | Flat (TimeBack averages alt-week 25\)     |  
| Vocabulary   |       10 | Base rate                                |  
| FastMath     |       10 | Base rate                                |

\- Coaches can override per-app XP per student.  
\- Coaches can set a "test out of grade by date" goal; daily target back-solves to  
  \`remaining\_xp / remaining\_school\_days\`.  
\- Pace status uses TimeBack's literal labels ("On Track", "Needs To Catch Up",  
  "Ahead") for base-rate students; richer \`PaceReport\` for personalized goals.  
\- Accuracy below 60% in any subject auto-flags the student.  
\- School days only — no weekends, holidays, or TSA breaks (Calendar A).

\#\# Recovery instructions for a future chat

1\. Read this README — find the \*\*Last completed checkpoint\*\* line.  
2\. Read the most recent commits on \`main\` for trajectory.  
3\. Resume from the next checkpoint per the build plan.

\#\# Setup

\`SETUP.md\` will be added at Checkpoint 7\.

\#\# Upstream

Forked from \[Alpha-School-SB/timeback-dashboard-v2\](https://github.com/alpha-school-sb/timeback-dashboard-v2).  
The original scraper is kept; this repo extends it with goal logic, Slack reports,  
calendar awareness, and TSA-specific config.

