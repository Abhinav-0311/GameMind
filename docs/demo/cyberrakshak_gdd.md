# CyberRakshak: The Ethical Hacker

## Project profile

| Field | Details |
| --- | --- |
| Engine | Unity 6000.2.7f2 |
| Main platform | PC |
| AR platform | Android |
| Package plan | One Unity project with separate PC and Android build targets |
| Genre | Low-poly 3D cyber-infiltration platformer with AR awareness tasks and optional VR challenge levels |
| One-line pitch | A cybersecurity intern infiltrates simulated systems, exposes vulnerabilities, and learns ethical hacking boundaries. |

## 1. High concept

CyberRakshak is a story-driven 3D platformer where the player controls Adi, a first-time cybersecurity intern at Rakshak Labs. Adi is guided by his supervisor Jay through digital sandbox missions. Each mission represents a cybersecurity problem such as weak passwords, phishing, malware, firewalls, QR scams, social engineering, and ransomware.

The player can approach missions through stealth, bold action, puzzle-solving, or speed. Cybersecurity concepts become mechanics instead of lectures: firewalls are literal walls of fire, malware becomes enemies, phishing becomes fake routes, and data is an objective to retrieve safely.

Jay is secretly using Adi to break into real systems. After the reveal, Adi works with cyber police to track Jay down and prove his innocence.

## 2. Target platforms

### PC main game

- Story Mode
- Sandbox platformer missions
- PowerRush high-score mode
- VR Breach Run challenge levels when hardware is available
- Progression, scoring, ratings, and analytics

### Android AR module

- AR CyberLens Weekly Audit
- Marker or card-based scanning tasks
- Device safety education
- Weekly leaderboard challenges

The AR mode must use printed markers, QR-style cards, or image targets for reliability. It must not depend on real object detection.

## 3. Core game pillars

1. Fun first: the game should feel like a platformer, not a classroom lesson.
2. Cybersecurity as gameplay: every cyber concept becomes a mechanic, enemy, route, or obstacle.
3. Player choice: missions support stealth, bold, puzzle, or speedrun approaches.
4. Ethical decision-making: the story distinguishes ethical hacking from illegal hacking.
5. Replayability: ratings, leaderboards, alternate paths, and PowerRush encourage replay.

## 4. Narrative summary

Adi joins Rakshak Labs as an ethical hacking intern. He is nervous because it is his first internship and he does not want to make a mistake. He meets Jay, a calm and skilled supervisor who places him inside a demo system to test his skills.

Jay guides Adi through sandbox levels where he infiltrates systems, retrieves target data, and exposes vulnerabilities. The missions appear to be normal training simulations, but Adi starts noticing real names, real data, odd server labels, and missing authorization notices.

By the ninth main level, Adi discovers that Jay has used him to enter real systems containing real user data. Cyber police catch Adi. To prove his innocence, he works with them to track Jay down. In the final level, Adi exposes Jay, helps arrest him, and earns a legitimate internship with cyber police.

## 5. Main characters

### Adi

Adi is the player character: a beginner ethical hacker represented as a blue-hat hacker. His growth appears through stronger tools, better decisions, and changing hat colours.

### Jay

Jay is Adi's supervisor at Rakshak Labs. He starts as a white-hat hacker and gradually shifts toward black-hat behaviour. His visual hat colour changes from white to black through the story.

### PATCH

PATCH is Adi's AI support tool. PATCH provides hints, warnings, mission reactions, and short cybersecurity explanations. PATCH must be funny, helpful, and warning-based rather than teacher-like. After Jay's betrayal, PATCH becomes Adi's trusted guide while he works with cyber police.

## 6. Core gameplay loop

1. Enter a mission.
2. Identify the target and environment.
3. Choose stealth, bold, puzzle, or speed approach.
4. Avoid or break security defences.
5. Retrieve evidence or data.
6. Expose the vulnerability.
7. Escape or complete the objective.
8. Receive a rating and feedback.
9. Unlock the next mission, tool, or story event.

## 7. Player approaches

### Stealth

Avoid detection, use hidden routes, disable alarms, and complete objectives quietly.

### Bold

Fight cyber defences directly, break barriers, and move quickly through danger.

### Puzzle

Solve access-control, firewall, route, or logic challenges.

### Speed

Complete the level quickly for time-based rewards at higher risk.

## 8. Rating system

Each mission awards one performance rating:

1. Flawless
2. Feasible
3. Acceptable
4. Intolerable
5. Back to Grad School

Ratings use detection count, damage caused, time taken, wrong interactions, optional objectives completed, data integrity preserved, and stealth or combat efficiency.

## 9. Story mode level plan

### Level 1: Training Sandbox

Focus: basic movement, traversal, loadout, combat, and mission structure. PATCH teaches core mechanics. Jay appears supportive and professional.

### Level 2: Password Vault

Focus: passwords and authentication. Weak-password gates break easily. Strong gates require correct password-token combinations.

### Level 3: Phishing Office

Focus: phishing and fake websites. Fake routes, fake login doors, suspicious signs, and urgency traps mislead the player.

### Level 4: Malware Warehouse

Focus: malware and suspicious downloads. Trojan crates, infected files, and malware enemies corrupt platforms.

### Level 5: Firewall Fortress

Focus: firewalls and access control. Firewalls are literal walls of fire. The player opens safe routes and blocks malicious paths.

### Level 6: QR Market

Focus: QR scams and digital-payment fraud. Some QR portals are safe while others redirect the player into traps.

### Level 7: Social Engineering Plaza

Focus: manipulation, impersonation, and trust. NPCs pretend to be admins, friends, or support agents to trick the player.

### Level 8: Ransomware Ruins

Focus: ransomware, backups, and locked data. Ransom locks freeze gates and platforms; backup keys restore access.

### Level 9: The Reveal

Focus: ethical boundaries. Adi learns that Jay used him to enter real systems. Cyber police catch Adi and Jay disappears.

### Level 10: Hunt Jay

Focus: combined threats and incident response. Adi works with cyber police to track Jay, face combined cyber threats, and expose him.

## 10. PATCH companion system

PATCH has two roles:

1. Narrative role: reacts to Jay, story events, and Adi's choices.
2. Gameplay role: provides hints, scans, warnings, and feedback.

Example PATCH lines:

- "That link is trying too hard. Check the URL before you trust it."
- "A file called homework_final_REAL_REAL.exe is already confessing."
- "Firewall ahead. Literal this time. Someone had fun with the simulation."
- "Adi, Jay said this was a demo server. These records look real."
- "Verify, block, backup, quarantine. You know the pattern now."

### PATCH implementation plan

Phase 1 uses fully scripted dialogue triggered by level start, wrong interaction, first enemy encounter, boss events, and level end.

Phase 2 uses rule-based dynamic dialogue based on player behaviour, repeated mistakes, stealth success, combat route, or low health.

AI-generated hint variations are optional only if time and reliability allow.

## 11. Wrong interaction mechanic

When the player interacts with a suspicious or wrong object, the game creates a consequence:

- Show a pop-up on screen.
- Reduce visibility.
- Spawn extra malware enemies.
- Make controls temporarily harder.
- Increase alarm level.
- Reduce the rating.

This makes cybersecurity mistakes visible through gameplay.

## 12. PowerRush mode

PowerRush is a replayable arcade mode. Cyber threats rush toward a system core; the player identifies and neutralizes them quickly.

### Scoring

- Correct action gives points.
- Fast response gives a bonus.
- Consecutive correct actions build combo.
- Wrong action breaks combo.
- Missed threats damage system health.

### Power-ups

- Firewall Blast
- 2FA Shield
- URL Scanner
- Quarantine Pulse
- Backup Restore

## 13. AR CyberLens Weekly Audit

The Android AR module uses marker-based scanning.

Weekly task: scan five input or access devices and learn safe use.

Example devices:

- Keyboard
- Mouse
- Webcam
- Microphone
- USB drive
- Bluetooth controller
- Phone

For each scan, the game shows the device, benefits, cybersecurity risks, safe usage tips, a short question or action, and leaderboard points.

### USB drive example

Benefits: easy file transfer, portable, works offline.

Risks: can carry malware, can support data theft, and unknown USB devices are dangerous.

Safe usage: do not plug in unknown USB drives; scan files before opening; disable auto-run; use trusted devices.

### AR leaderboard scoring

- Scan device: +50
- Correct risk identification: +100
- Correct safety action: +100
- Weekly five-device completion: +300
- Wrong answer: -50

## 14. VR Breach Run

VR Breach Run is a PC VR challenge mode with three or four parkour/platforming levels.

- Firewall Run: jump across firewall platforms, dodge firewalls, and activate secure gates.
- Malware Mines VR: parkour through infected tunnels, avoid malware enemies, and destroy corrupted files.
- Phishing Skyline: jump between floating URL platforms; fake platforms collapse or redirect the player.
- Root Virus Core VR: combined-threat parkour with pop-ups, malware, firewalls, and a final virus core.

VR controls include headset look, controller movement, jump, grab or interact, scanner tool, and quarantine action. Levels should be short and checkpointed for testing.

## 15. Combined Unity package plan

The project uses Unity 6000.2.7f2 as one main Unity project.

Build targets:

1. PC build for Story Mode, PowerRush, and VR Breach Run.
2. Android build for AR CyberLens Weekly Audit.

Shared systems include the cyber-threat database, scoring rules, player profile, leaderboard logic, UI style, cybersecurity content, and PATCH dialogue content.

Separate systems include PC movement and platform controls, VR interaction controls, and Android AR camera and image tracking.

## 16. Cybersecurity learning outcomes

The player should understand strong password practices, phishing signs, malware risks, firewall purpose, QR and payment scam risks, social engineering tactics, ransomware and backup importance, ethical versus unethical hacking boundaries, and safe use of common devices through AR tasks.

## 17. Research and evaluation

Evaluate the project using pre-test and post-test cybersecurity awareness scores, wrong-interaction count, threat-recognition accuracy, level completion time, rating distribution, AR weekly-task score, player-engagement survey, and usability survey.

Possible paper direction: "Design and Evaluation of a Narrative 3D Cybersecurity Platformer with AR-Based Device Safety Awareness."

## 18. Must-have, should-have, could-have

### Must-have

- PC 3D Story Mode prototype
- At least eight to ten story levels or a polished vertical slice
- PATCH scripted dialogue
- Wrong-interaction pop-up mechanic
- Rating system
- PowerRush mode
- Android AR marker-scanning prototype

### Should-have

- Full ten-level story arc
- Weekly AR leaderboard tasks
- Jay betrayal sequence
- Combined-threat final level
- Shared scoring and analytics

### Could-have

- VR Breach Run with three or four levels
- Dynamic PATCH dialogue
- AI-generated hint variations
- Online leaderboard
- More AR device categories

## 19. Risks and controls

| Risk | Control |
| --- | --- |
| Project becomes too large | Focus first on PC Story Mode and one AR prototype. |
| AR object detection is unreliable | Use marker-based image tracking instead of real object detection. |
| VR levels take too much testing | Keep VR levels short, separate, and optional until the core game is stable. |
| Game teaches unsafe hacking | Keep hacking abstract, fictional, ethical, awareness-focused, and defensive. |
| Story becomes text-heavy | Use short dialogue, logs, and small cinematics instead of long cutscenes. |

## 20. Final positioning

CyberRakshak: The Ethical Hacker is a low-poly digital sandbox platformer about ethical hacking, cyber awareness, and trust. The project combines PC platforming missions, Android AR weekly device-safety tasks, a companion guide, a betrayal story, rating-based replayability, and optional VR parkour challenges.

The project is designed to be fun first while supporting measurable cybersecurity learning outcomes for a capstone research paper.
