# CyberRakshak Runtime Extension

## Status

Proposed runtime companion for the CyberRakshak MVP. It translates the approved GDD direction into small, concrete records that GameMind can materialize for a playable vertical slice.

## Runtime scope

The first runtime slice is the PC Training Sandbox and Password Vault sequence. It remains fictional, defensive, and educational. Jay introduces the mission, PATCH provides contextual guidance, and Adi is the player-facing protagonist.

## NPC runtime profiles

NPC Jay: Jay is the Rakshak Labs supervisor and the quest giver for the early training missions. He speaks calmly, uses short operational instructions, and initially presents every task as an authorised sandbox exercise.

NPC PATCH: PATCH is Adi's AI support tool. PATCH gives concise warnings, explains safe choices without lecturing, and reacts when the player selects a suspicious route or object.

NPC Adi: Adi is the player character and a first-time ethical-hacking intern. His dialogue is brief, curious, and focused on learning through defensive problem solving.

## Quest runtime records

| Quest | Objective | Reward |
| --- | --- | --- |
| Training Sandbox Orientation | Speak with Jay, complete the movement and scanner tutorial, and identify the authorised training terminal. | Unlock the Scanner tool and Password Vault. |
| Password Vault Evidence | Inspect password-token clues, choose the safe access route, and retrieve protected training evidence without triggering the alarm. | Unlock the Phishing Office briefing and a Feasible rating checkpoint. |
| Phishing Office Warning | Follow PATCH's warning, reject the fake login route, and tag the suspicious page as a phishing threat. | Unlock the defensive analysis log and the next story mission. |

## Runtime world state

The initial state has the Training Sandbox unlocked, the Password Vault locked until the tutorial is complete, and the player scanner unavailable until Jay confirms the first objective. Each quest completion must unlock only the next approved mission step.

## Presentation contract

Jay uses calm briefing and acknowledgement states. PATCH uses warning and guidance states. Adi uses attentive and uncertain states. A client may map these state names to its own animation, UI, or audio implementation.

## Verification checklist

1. The client can load Jay, PATCH, and Adi from the runtime bundle.
2. The first quest is assigned by Jay and can be accepted without a network service.
3. PATCH can provide a contextual progressive hint after a wrong-route or hint request event.
4. Quest progression changes only the stated local world-state gates.
