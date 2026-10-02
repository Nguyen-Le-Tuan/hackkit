# Pitch and submission (fill after kickoff)

Demo and presentation are usually the biggest share of the score. Prepare this in parallel with
the build, not in the last 20 minutes.

## Judging criteria (copy from the kickoff, with weights)
| Criterion | Weight | What we show for it |
|-----------|--------|---------------------|
| <e.g. impact> | <%> | |
| <e.g. feasibility> | <%> | |
| <e.g. demo> | <%> | |
| <e.g. presentation> | <%> | |

## Pitch outline (adjust to the real slot, e.g. 3 min + Q&A)
1. Pain (~30 s): who has the problem, one concrete example, one number if we have a real one.
2. Live demo (~90 s): the exact flow from `docs/spec.md`, on sample data, no detours.
3. How it works (~30 s): the LLM extracts, plain rules decide. Say what is real and what is mocked.
4. Impact and next step (~30 s): who uses it Monday morning, what we would build next.

## Demo checklist
- [ ] `make demo` works offline (fake provider) and the real-model run works with a key.
- [ ] Sample inputs are ready to paste; the happy path was rehearsed three times.
- [ ] A screen recording of the full flow exists as a backup.
- [ ] One person drives the demo, one person talks; swap roles for Q&A.

## Q&A prep (everyone must be able to answer without the agents)
- What exactly does the LLM do, and what is deterministic code?
- What data did we use? (public or synthetic only)
- What happens when the model is wrong or unsure? (review flags)
- What did we not build, and why?
- How did we use AI tools and the hackkit template? (be upfront)

## Submission checklist (do it at least 30 min before the deadline)
- [ ] Devpost: title, tagline, description, links, video, screenshots.
- [ ] Repo link works for judges (public or shared as required).
- [ ] The Devpost text discloses: hackkit template (pre-existing framework) and AI coding tools.
- [ ] Team members are listed and the submission is saved as final.
