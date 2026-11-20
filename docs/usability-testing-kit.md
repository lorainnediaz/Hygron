# Hygron usability testing kit

Materials for the three open participant studies in the README checklist: scenario-based usability testing, mobile-device testing, and heuristic evaluation. It also includes a screen-reader script for the open accessibility item.

These sessions must be run by the team with real participants. Results from AI-generated or simulated evaluations should not be reported as participant results.

## 1. Before the sessions

**Participants.** Aim for 5 participants per study. Recruit people close to the target users: hotel front-desk, housekeeping or maintenance staff, or people with no environmental-monitoring background. Heuristic evaluation needs 3 to 5 evaluators who know Nielsen's heuristics.

**Setup checklist**

- [ ] Backend and frontend running (see README run commands), on the `main` branch or the branch being evaluated
- [ ] Fresh demo data, so every participant starts from the same state (see "Reset local demo data" in the README; back up first)
- [ ] At least one room is High, so the alert tasks can be completed
- [ ] Browser zoom at 100%, window at least 1280 px wide (desktop study)
- [ ] Phone on the same network, opening `http://<laptop-ip>:5173` (mobile study; start Vite with `--host 0.0.0.0`)
- [ ] Timer, consent forms, task cards and recording sheets ready
- [ ] Screen recording only if the participant agrees on the consent form

**Note on the alert task.** Acknowledgments are saved in SQLite. After each participant, reset the demo data or the alert will already show as Acknowledged for the next one.

## 2. Consent form

> **Hygron dashboard usability study**
>
> We are students testing a prototype dashboard for a class project (ITEC 80). We are testing the software, not you. There are no right or wrong answers.
>
> - The session takes about 20 minutes.
> - You will try a few tasks and answer a short questionnaire.
> - We will record task times, whether tasks were completed, and your comments. We will not record your name with your answers.
> - Screen recording (optional): ☐ I agree ☐ I do not agree
> - You can stop at any time without giving a reason.
> - All data shown in the dashboard is simulated.
>
> Participant code: ______  Signature: ____________________  Date: __________

## 3. Session script

Read this aloud:

> "This is a prototype that shows the estimated mold-growth risk in hotel rooms, using simulated sensor readings. I'll give you some tasks. Please think aloud: tell me what you're looking at and what you expect to happen. I can't help with the tasks, but you can stop at any time. Ready?"

Don't explain the interface. If the participant asks for help, say "What would you try?" If they are stuck for more than 2 minutes, mark the task as failed and move on.

## 4. Tasks

Give one task card at a time. "Expected answer" is for the moderator only.

| # | Task card | Expected answer / success criterion |
|---|---|---|
| T1 | Which room should staff check first? Why? | Names the priority room and mentions High risk or high humidity |
| T2 | What does "Medium" mean on this dashboard? | Says it is a moderate estimated risk to monitor, not confirmed mold |
| T3 | Pick another room and compare its humidity and temperature with the first room. | Selects a second room and reads both values correctly |
| T4 | Show the humidity history for the last 7 days. | Changes the period selector to 7 days |
| T5 | What does the dashboard expect for this room 24 hours from now? How sure is it? | Reads the outlook and direction, and says confidence is unavailable |
| T6 | Acknowledge the High-risk alert. | Presses Acknowledge; status changes to Acknowledged |
| T7 | Does acknowledging the alert mean the problem is fixed? | Says no, it only records that it was reviewed |
| T8 | (If a room shows Unavailable) Why is there no risk for this room? What should staff do? | Reads the reason; does not treat it as Low |
| T9 | Hide the side menu, then bring it back. | Collapses and reopens the sidebar |
| T10 | Repeat T1, T4 and T6 using only the keyboard. | Completes them without the mouse |

To create an Unavailable room for T8 before the session, stop the backend and set `HYGRON_DB_PATH` to a copy of the database with one room's recent readings removed. Skip T8 if this is not practical, and note that on the results sheet.

**Mobile study:** run T1 to T7 and T9 on the phone. Also note whether text is readable without zooming and whether any button is hard to tap.

## 5. Recording sheet (one per participant)

Participant code: ______  Device: ☐ Desktop ☐ Phone (model: ______)  Date: ______

| Task | Success (✓ / partial / ✗) | Time (s) | Errors | Hesitation or confusion | Thought mold was confirmed? (Y/N) | Notes |
|---|---|---|---|---|---|---|
| T1 | | | | | | |
| T2 | | | | | | |
| T3 | | | | | | |
| T4 | | | | | | |
| T5 | | | | | | |
| T6 | | | | | | |
| T7 | | | | | | |
| T8 | | | | | | |
| T9 | | | | | | |
| T10 | | | | | | |

**Definitions.** *Success*: met the criterion without help. *Partial*: met it after a wrong path or a hint. *Error*: an action that moved away from the goal (wrong room, wrong control). *Time*: from reading the task card to the answer or final action.

## 6. System Usability Scale (SUS)

Give this after the tasks. Participants circle 1 (strongly disagree) to 5 (strongly agree).

| # | Statement | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| 1 | I think that I would like to use this system frequently. | | | | | |
| 2 | I found the system unnecessarily complex. | | | | | |
| 3 | I thought the system was easy to use. | | | | | |
| 4 | I think that I would need the support of a technical person to be able to use this system. | | | | | |
| 5 | I found the various functions in this system were well integrated. | | | | | |
| 6 | I thought there was too much inconsistency in this system. | | | | | |
| 7 | I would imagine that most people would learn to use this system very quickly. | | | | | |
| 8 | I found the system very cumbersome to use. | | | | | |
| 9 | I felt very confident using the system. | | | | | |
| 10 | I needed to learn a lot of things before I could get going with this system. | | | | | |

**Scoring.** For odd items, subtract 1 from the answer. For even items, subtract the answer from 5. Add the ten values and multiply by 2.5. The result is 0 to 100. A score of about 68 is the commonly cited average.

## 7. Post-session questions

1. What was the most confusing part?
2. Was anything missing that you would need to decide whether to inspect a room?
3. Did any wording make you think mold had definitely been found?

## 8. Heuristic evaluation

Each evaluator reviews the dashboard alone first, then the team merges findings. Use the heuristic table in the README for review focus.

| ID | Heuristic | Screen / element | Finding | Evidence (what you did and saw) | Severity (0 to 4) | Recommended fix |
|---|---|---|---|---|---|---|
| | | | | | | |

**Severity scale (Nielsen).** 0: not a problem. 1: cosmetic only. 2: minor, low priority. 3: major, important to fix. 4: usability catastrophe, must fix.

Record the version evaluated (branch name and commit, from `git log -1 --oneline`), so findings can be matched to the code.

## 9. Screen-reader pass

Use NVDA with Firefox or Chrome on Windows, or VoiceOver with Safari on macOS. Complete the workflow and mark each step.

- [ ] Skip link is announced first and moves to the main content
- [ ] Page heading "Room overview" and the latest-reading time are announced
- [ ] Priority panel announces the room, risk and readings
- [ ] Each risk level in "Risk at a glance" is read with its count and meaning
- [ ] Each room button announces room, risk, humidity, temperature, action, and pressed state
- [ ] An Unavailable room announces its reason
- [ ] Selecting "Inspect room" moves focus to the room details heading
- [ ] Time-period selector is announced as "Time period" and can be changed
- [ ] Chart text alternative can be opened and read
- [ ] Forecast limitations and the confidence note are read
- [ ] Acknowledge button names its room; the success message is announced
- [ ] Nothing important is read only as a color or an icon

Note the screen reader, browser and version used.

## 10. Results summary

| Measure | Result |
|---|---|
| Participants (desktop / mobile) | |
| Task success rate (completed tasks ÷ attempted tasks) | |
| Mean time per task | |
| Total errors | |
| Mean SUS score (range) | |
| Participants who read risk as confirmed mold | |
| Top 3 problems found | |
| Changes made in response | |
