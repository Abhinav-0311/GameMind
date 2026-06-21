using UnityEngine;
using GameMind.Contracts;

namespace GameMind
{
    [RequireComponent(typeof(Animator))]
    public class NpcInteractionController : MonoBehaviour
    {
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

            // Map and trigger animations
            if (!string.IsNullOrEmpty(response.suggested_animation))
            {
                TriggerAnimation(response.suggested_animation);
            }
            
            // Handle emotional changes (e.g. adjust material colors, floating symbols, etc.)
            if (response.npc_emotions != null)
            {
                Debug.Log($"Emotions Updated -> Trust: {response.npc_emotions.trust}, Anger: {response.npc_emotions.anger}, Loyalty: {response.npc_emotions.loyalty}");
            }
        }

        public void TriggerAnimation(string animationName)
        {
            if (animator == null) return;

            // Clear any active trigger flags if necessary, or set trigger
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
