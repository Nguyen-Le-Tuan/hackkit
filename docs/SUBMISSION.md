# Devpost submission (draft here, paste into Devpost at T−1:00)

Online judges often read only this page and watch the video. Lead with the result, not the stack.
Keep each section short; use the screenshots from `make shots`.

## Checklist
- [ ] Title and one-line tagline (the same words as the title slide)
- [ ] Cover image: `docs/pitch/shots/home.png` (or a better shot)
- [ ] Video ≤ 3 min, uploaded unlisted (YouTube/Vimeo): `make demo-video` + voice-over if time allows
- [ ] "Try it" link: `make pages` (static demo on GitHub Pages) or the live server URL
- [ ] Repo link, public when the rules require it (`make public` runs the guard first)
- [ ] Every team member added on Devpost
- [ ] Prize tracks / sponsor challenges selected (each one we qualify for)
- [ ] "Built with" tags filled in
- [ ] Disclosure: hackkit template (pre-existing) and AI coding tools used
- [ ] Submitted as FINAL; confirmation screenshot saved

---

## Inspiration
Who has the problem, in their words. One real number if you have it.

## What it does
Three sentences. What the user puts in, what they get back, why it can be trusted.

## How we built it
- An LLM extracts structured data (schema-validated, with confidence and review flags).
- Deterministic, tested Python does the math and rules: the model never decides a number.
- FastAPI backend, plain HTML/CSS/JS front end, runs offline from saved results.
- Data: <public sources, with licences>. Sponsor tech: <what we used and how>.

## Challenges we ran into
One or two honest ones, and what we did about them.

## Accomplishments that we're proud of
The thing that works end to end. Accuracy from `make eval`. Tests.

## What we learned
Short and specific.

## What's next
The pilot with the partner, then the bigger vision.

## Built with
python · fastapi · pydantic · javascript · <llm provider> · <sponsor apis> · <data sources>
