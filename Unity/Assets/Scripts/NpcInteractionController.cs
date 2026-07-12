using UnityEngine;
using GameMind.Contracts;

namespace GameMind
{
    [RequireComponent(typeof(Animator))]
    public class NpcInteractionController : MonoBehaviour
    {
        private static readonly System.Collections.Generic.HashSet<string> AllowedAnimations = new System.Collections.Generic.HashSet<string>
        {
            "idle", "talk", "agree", "disagree", "gesture"
        };

        private Animator animator;

        private void Awake()
        {
            animator = GetComponent<Animator>();
        }

        public void HandleDialogueResponse(DialogueChatResponse response)
        {
            if (response == null) return;

            // Log message
            Debug.Log($"[{response.npc_slug}]: {response.response_text}");

            // Map and trigger animations with allowlist checks and dominant emotion fallback
            string animationName = response.suggested_animation;
            if (string.IsNullOrEmpty(animationName) || !AllowedAnimations.Contains(animationName.ToLower()))
            {
                // Fallback to dominant emotion mapping
                if (response.npc_emotions != null)
                {
                    animationName = GetDominantEmotionAnimation(response.npc_emotions);
                    Debug.Log($"Animation '{response.suggested_animation}' not allowed. Mapped to dominant emotion: '{animationName}'");
                }
                else
                {
                    animationName = "idle";
                }
            }

            TriggerAnimation(animationName);
            
            // Handle emotional changes (e.g. adjust material colors, floating symbols, etc.)
            if (response.npc_emotions != null)
            {
                Debug.Log($"Emotions Updated -> Trust: {response.npc_emotions.trust}, Anger: {response.npc_emotions.anger}, Loyalty: {response.npc_emotions.loyalty}");
            }
        }

        private string GetDominantEmotionAnimation(NPCEmotions emotions)
        {
            float maxVal = emotions.trust;
            string dominant = "trust";

            if (emotions.anger > maxVal) { maxVal = emotions.anger; dominant = "anger"; }
            if (emotions.fear > maxVal) { maxVal = emotions.fear; dominant = "fear"; }
            if (emotions.curiosity > maxVal) { maxVal = emotions.curiosity; dominant = "curiosity"; }
            if (emotions.loyalty > maxVal) { maxVal = emotions.loyalty; dominant = "loyalty"; }

            switch (dominant)
            {
                case "trust": return "agree";
                case "anger": return "disagree";
                case "fear": return "gesture";
                case "curiosity": return "talk";
                case "loyalty": return "agree";
                default: return "idle";
            }
        }

        public void TriggerAnimation(string animationName)
        {
            if (animator == null) return;
            if (animator.runtimeAnimatorController == null)
            {
                Debug.Log($"NPC animation '{animationName}' skipped because no Animator Controller is assigned.");
                return;
            }

            try
            {
                animator.SetTrigger(animationName);
                Debug.Log($"Triggered NPC Animation: {animationName}");
            }
            catch (System.Exception ex)
            {
                Debug.LogWarning($"Could not set animation trigger '{animationName}': {ex.Message}");
            }
        }
    }
}
