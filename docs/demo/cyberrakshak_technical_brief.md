# CyberRakshak Technical Brief

## Status

Proposed MVP implementation decisions generated from the CyberRakshak GDD. These decisions are intentionally explicit so the team can revise them through GameMind if the project direction changes.

## Source context

- Primary GDD: `cyberrakshak_gdd.md`, revision 1
- Engine: Unity 6000.2.7f2
- Game direction: story-driven 3D ethical-cybersecurity platformer

## MVP delivery scope

The MVP is a Windows PC Story Mode vertical slice. It includes the Training Sandbox, Password Vault, and one complete mission loop: explore, identify a threat, solve a defensive cybersecurity challenge, retrieve evidence, receive feedback, and unlock the next mission.

Android AR is deferred to a single marker-based prototype after the PC vertical slice is stable. Optional VR Breach Run content is deferred until the PC loop meets the performance and usability targets. PowerRush and online leaderboards are post-MVP work.

## Performance target

The PC vertical slice must target 60 frames per second at 1080p on the development target machine. Each playable level must contain a checkpoint, a restart path, and a measured completion time. A playtest build is not accepted until the mission can be completed without a frame-time spike that prevents player input.

## Online feature boundary

The MVP is offline-first. It has no player accounts, remote leaderboard, cloud save, live matchmaking, or required web service. Ratings, wrong-interaction counts, completion time, and threat-recognition results are stored locally for playtest review only. If a later online feature is unavailable, the player must still be able to play every MVP mission and receive local feedback.

## Accessibility baseline

The MVP must provide subtitles with speaker labels, adjustable text size, high-contrast UI, non-colour threat indicators, remappable keyboard controls, controller support, pause-anywhere behaviour, and reduced-motion options for camera shake and flashing effects. Each milestone playtest must include one keyboard-only pass and one pass with the accessibility settings enabled.

## Defensive content boundary

All cybersecurity interactions remain abstract, fictional, defensive, and awareness-focused. The game must not provide real exploit instructions, credentials, targeting steps, or actionable intrusion procedures.

## Verification checklist

1. Build and complete the PC vertical slice offline.
2. Confirm the mission loop can be finished using keyboard and controller.
3. Verify subtitles, text scaling, contrast, and reduced-motion settings.
4. Record local playtest metrics without transmitting player data.
5. Test the optional AR prototype separately after the PC loop is stable.
