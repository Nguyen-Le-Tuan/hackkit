# Pitch kit: from the running app to slides, video and Devpost in three commands

Judges score what they see. Start this at kickoff, not in the last hour: the commands below
rebuild everything from the real app in a few minutes, so you can iterate all day.

```bash
pip install -e ".[pitch]" && playwright install chromium   # once per laptop
make shots        # docs/pitch/shots/*.png   real screenshots (from shots.toml)
make deck         # docs/pitch/out/deck.pptx + deck.pdf + previews (from deck.toml)
make demo-video   # docs/pitch/out/demo.mp4  captioned, with a visible cursor (from demo_flow.toml)
make pitch        # all three, in order
```

| File | What you edit | Why it wins points |
|---|---|---|
| `shots.toml` | Which pages to capture, after which clicks | Slides and README always show the REAL, current app |
| `deck.toml` | One `[[slide]]` per slide: words, image, notes, seconds, rubric | Short slides, timing checked against the slot, every rubric category covered |
| `demo_flow.toml` | The demo as steps + captions | A backup video that never fails on stage, and the Devpost video |
| `script.md` | What each person says, second by second | Nobody improvises the most important 4 minutes |
| `../SUBMISSION.md` | The Devpost page | Online judges read this and watch the video, often nothing else |

## Timeline (fill the real times at kickoff)

| When | Pitch owner does |
|---|---|
| T+0:30 | Rubric table below; the "10-second moment"; one impact number to find |
| T+1:30 | `make shots` on the ugly first version; deck v0 with titles only |
| T+2:30 | Deck v1 with real screenshots; `script.md` first full pass |
| T−1:30 | Freeze. `make pitch`; rehearse 3× with a timer |
| T−1:00 | Video uploaded (unlisted), Devpost page complete |
| T−0:30 | Submitted. Screenshot of the confirmation saved |

## Rubric map (copy the real criteria at kickoff)

| Criterion | Weight | Slide / demo moment that scores it | Evidence |
|---|---|---|---|
| Impact | | Problem + Impact slides | one sourced number |
| Innovation | | How it works + the 10-second moment | what others will not have |
| Presentation | | Title, flow, timing | rehearsed 3× |
| Future potential | | What's next | pilot with the partner |
| Execution ("no mistakes") | | Live demo + "every number is checked" | tests, evals, `make verify` |

## Demo checklist
- [ ] `make doctor` passes on the demo laptop, and `#/doctor` passes in its browser.
- [ ] `make snapshot` was run with the REAL model; `make web` works with Wi-Fi off.
- [ ] Inputs to paste are ready; the happy path was rehearsed three times on the demo laptop.
- [ ] `docs/pitch/out/demo.mp4` is open in a second window as the backup.
- [ ] One person drives, one talks; swap for Q&A.

## Q&A prep (everyone answers without the agents)
- What exactly does the LLM do, and what is deterministic code?
- Where does each number come from? What is real and what is a demo value (red)?
- What happens when the model is wrong or unsure? (review flags)
- What did we not build, and why?
- How did we use AI tools and the hackkit template? (be upfront)
