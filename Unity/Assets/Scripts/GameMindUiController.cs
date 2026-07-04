using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using GameMind.Contracts;

namespace GameMind
{
    public class GameMindUiController : MonoBehaviour
    {
        [SerializeField] private string targetBlueprintId = "00000000-0000-0000-0000-000000000000"; // Set dynamically or in editor

        // Stored materialized details
        private List<NpcProfileDto> materializedNpcs = new List<NpcProfileDto>();
        private List<QuestDto> materializedQuests = new List<QuestDto>();
        private string activeQuestId = "";
        private int currentHintLevel = 1;

        // UI references generated programmatically
        private Text statusText;
        private GameObject dialoguePanel;
        private Text dialogueText;
        private GameObject questPanel;
        private Text questTitleText;
        private Text questDescText;
        private Button acceptQuestButton;
        private GameObject hintPanel;
        private Text hintText;
        private Button requestHintButton;
        private Button interactButton;
        private Button closeDialogueButton;

        private NpcInteractionController eldrinController;

        private void Start()
        {
            // Find NPC Eldrin interaction controller in the scene
            NpcInteractionController npc = FindFirstObjectByType<NpcInteractionController>();
            if (npc != null)
            {
                eldrinController = npc;
            }

            CreateCanvasUI();
            StartCoroutine(ConnectToBackend());
        }

        private IEnumerator ConnectToBackend()
        {
            statusText.text = "Status: Connecting to GameMind...";
            statusText.color = Color.yellow;

            // Wait one frame to ensure API client instance is awake
            yield return null;

            if (GameMindApiClient.Instance == null)
            {
                statusText.text = "Status: ApiClient Missing";
                statusText.color = Color.red;
                yield break;
            }

            yield return GameMindApiClient.Instance.GetRuntimeBundle(
                targetBlueprintId,
                OnBundleLoaded,
                OnBundleError
            );
        }

        private void OnBundleLoaded(BlueprintRuntimeBundleResponse bundle)
        {
            materializedNpcs = bundle.npcs;
            materializedQuests = bundle.quests;

            if (materializedNpcs.Count == 0 && materializedQuests.Count == 0)
            {
                statusText.text = "Status: Empty Bundle (No Materialization)";
                statusText.color = Color.yellow;
                return;
            }

            statusText.text = "Status: Connected (Runtime Ready)";
            statusText.color = Color.green;

            // Enable interaction HUD
            interactButton.gameObject.SetActive(true);

            // Populate Quest Panel if quests are materialized
            if (materializedQuests.Count > 0)
            {
                QuestDto quest = materializedQuests[0];
                activeQuestId = quest.id;
                questTitleText.text = quest.title;
                questDescText.text = $"{quest.description}\n\nRewards: {quest.gold_reward} Gold, {quest.xp_reward} XP";
                questPanel.SetActive(true);
            }
        }

        private void OnBundleError(ErrorEnvelope error)
        {
            statusText.text = $"Status: Error ({error.error.code})";
            statusText.color = Color.red;
            Debug.LogError($"[GameMind UI] Connection failed: {error.error.message}");
        }

        private void InteractWithEldrin()
        {
            if (materializedNpcs.Count == 0) return;

            string npcSlug = "npc-eldrin";
            // Find Eldrin in materialized NPC list to match slug
            foreach (var npc in materializedNpcs)
            {
                if (npc.slug.Contains("eldrin"))
                {
                    npcSlug = npc.slug;
                    break;
                }
            }

            statusText.text = "Status: Querying Eldrin...";
            StartCoroutine(GameMindApiClient.Instance.SendChatDialogue(
                npcSlug,
                "Who is King Arven?",
                null,
                (response) => {
                    statusText.text = "Status: Connected (Runtime Ready)";
                    dialogueText.text = response.response_text;
                    dialoguePanel.SetActive(true);

                    if (eldrinController != null)
                    {
                        eldrinController.HandleDialogueResponse(response);
                    }
                },
                OnBundleError
            ));
        }

        private void AcceptQuest()
        {
            if (string.IsNullOrEmpty(activeQuestId)) return;

            statusText.text = "Status: Accepting Quest...";
            StartCoroutine(GameMindApiClient.Instance.AcceptQuest(
                activeQuestId,
                (response) => {
                    statusText.text = "Status: Connected (Runtime Ready)";
                    acceptQuestButton.gameObject.SetActive(false); // Accepted!
                    
                    // Unlock Progressive Hints UI
                    hintPanel.SetActive(true);
                    hintText.text = "Quest Accepted! Press Request Hint to load subtle help.";
                    Debug.Log("Quest accepted successfully. Hints unlocked.");
                },
                OnBundleError
            ));
        }

        private void RequestHint()
        {
            if (string.IsNullOrEmpty(activeQuestId)) return;

            statusText.text = $"Status: Fetching Hint Level {currentHintLevel}...";
            StartCoroutine(GameMindApiClient.Instance.GenerateHint(
                activeQuestId,
                currentHintLevel,
                (response) => {
                    statusText.text = "Status: Connected (Runtime Ready)";
                    hintText.text = $"[Level {response.hint_level} Hint]: {response.hint}";
                    
                    // Increment hint level for progression, looping back to 1 if we exceed level 3
                    currentHintLevel = currentHintLevel >= 3 ? 1 : currentHintLevel + 1;
                    
                    // Start brief cooldown timer lock
                    StartCoroutine(HintCooldownTimer(5));
                },
                OnBundleError
            ));
        }

        private IEnumerator HintCooldownTimer(int seconds)
        {
            requestHintButton.interactable = false;
            for (int i = seconds; i > 0; i--)
            {
                requestHintButton.GetComponentInChildren<Text>().text = $"Cooldown ({i}s)";
                yield return new WaitForSeconds(1f);
            }
            requestHintButton.interactable = true;
            requestHintButton.GetComponentInChildren<Text>().text = "Request Hint";
        }

        private void CloseDialogue()
        {
            dialoguePanel.SetActive(false);
        }

        // Programmatically generate a complete, responsive canvas UI styled in minimalist dark mode
        private void CreateCanvasUI()
        {
            GameObject canvasObj = new GameObject("GameMindCanvas");
            Canvas canvas = canvasObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvasObj.AddComponent<CanvasScaler>();
            canvasObj.AddComponent<GraphicRaycaster>();

            // 1. Status Indicator Text
            GameObject statusObj = new GameObject("StatusText");
            statusObj.transform.SetParent(canvasObj.transform, false);
            statusText = statusObj.AddComponent<Text>();
            statusText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            statusText.fontSize = 14;
            statusText.alignment = TextAnchor.UpperRight;
            RectTransform statusRect = statusText.GetComponent<RectTransform>();
            statusRect.anchorMin = new Vector2(1, 1);
            statusRect.anchorMax = new Vector2(1, 1);
            statusRect.pivot = new Vector2(1, 1);
            statusRect.anchoredPosition = new Vector2(-20, -20);
            statusRect.sizeDelta = new Vector2(400, 30);

            // 2. Interact with Eldrin Trigger Button
            GameObject interactObj = new GameObject("InteractButton");
            interactObj.transform.SetParent(canvasObj.transform, false);
            interactButton = interactObj.AddComponent<Button>();
            Image btnImg = interactObj.AddComponent<Image>();
            btnImg.color = new Color(0.2f, 0.2f, 0.2f, 0.9f);
            GameObject interactTextObj = new GameObject("Text");
            interactTextObj.transform.SetParent(interactObj.transform, false);
            Text btnText = interactTextObj.AddComponent<Text>();
            btnText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            btnText.text = "TALK TO ELDRIN";
            btnText.fontSize = 12;
            btnText.alignment = TextAnchor.MiddleCenter;
            btnText.color = Color.white;
            RectTransform interactRect = interactObj.GetComponent<RectTransform>();
            interactRect.anchorMin = new Vector2(0.5f, 0.5f);
            interactRect.anchorMax = new Vector2(0.5f, 0.5f);
            interactRect.anchoredPosition = new Vector2(0, -50);
            interactRect.sizeDelta = new Vector2(150, 40);
            interactButton.onClick.AddListener(InteractWithEldrin);
            interactButton.gameObject.SetActive(false);

            // 3. Dialogue Panel (bottom overlay)
            dialoguePanel = new GameObject("DialoguePanel");
            dialoguePanel.transform.SetParent(canvasObj.transform, false);
            Image dlgBg = dialoguePanel.AddComponent<Image>();
            dlgBg.color = new Color(0.08f, 0.08f, 0.08f, 0.95f);
            RectTransform dlgRect = dialoguePanel.GetComponent<RectTransform>();
            dlgRect.anchorMin = new Vector2(0.5f, 0);
            dlgRect.anchorMax = new Vector2(0.5f, 0);
            dlgRect.pivot = new Vector2(0.5f, 0);
            dlgRect.anchoredPosition = new Vector2(0, 30);
            dlgRect.sizeDelta = new Vector2(600, 150);

            GameObject dlgTextObj = new GameObject("Text");
            dlgTextObj.transform.SetParent(dialoguePanel.transform, false);
            dialogueText = dlgTextObj.AddComponent<Text>();
            dialogueText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            dialogueText.fontSize = 12;
            dialogueText.color = Color.white;
            dialogueText.alignment = TextAnchor.UpperLeft;
            RectTransform dlgTextRect = dialogueText.GetComponent<RectTransform>();
            dlgTextRect.anchorMin = new Vector2(0, 0);
            dlgTextRect.anchorMax = new Vector2(1, 1);
            dlgTextRect.offsetMin = new Vector2(20, 20);
            dlgTextRect.offsetMax = new Vector2(-20, -40);

            GameObject closeDlgObj = new GameObject("CloseButton");
            closeDlgObj.transform.SetParent(dialoguePanel.transform, false);
            closeDialogueButton = closeDlgObj.AddComponent<Button>();
            Image clsImg = closeDlgObj.AddComponent<Image>();
            clsImg.color = new Color(0.2f, 0.2f, 0.2f, 0.9f);
            GameObject clsTextObj = new GameObject("Text");
            clsTextObj.transform.SetParent(closeDlgObj.transform, false);
            Text clsText = clsTextObj.AddComponent<Text>();
            clsText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            clsText.text = "CLOSE";
            clsText.fontSize = 10;
            clsText.alignment = TextAnchor.MiddleCenter;
            clsText.color = Color.white;
            RectTransform clsRect = closeDlgObj.GetComponent<RectTransform>();
            clsRect.anchorMin = new Vector2(1, 1);
            clsRect.anchorMax = new Vector2(1, 1);
            clsRect.pivot = new Vector2(1, 1);
            clsRect.anchoredPosition = new Vector2(-10, -10);
            clsRect.sizeDelta = new Vector2(60, 25);
            closeDialogueButton.onClick.AddListener(CloseDialogue);
            dialoguePanel.SetActive(false);

            // 4. Quest Panel (left overlay)
            questPanel = new GameObject("QuestPanel");
            questPanel.transform.SetParent(canvasObj.transform, false);
            Image qstBg = questPanel.AddComponent<Image>();
            qstBg.color = new Color(0.1f, 0.1f, 0.1f, 0.95f);
            RectTransform qstRect = questPanel.GetComponent<RectTransform>();
            qstRect.anchorMin = new Vector2(0, 0.5f);
            qstRect.anchorMax = new Vector2(0, 0.5f);
            qstRect.pivot = new Vector2(0, 0.5f);
            qstRect.anchoredPosition = new Vector2(30, 0);
            qstRect.sizeDelta = new Vector2(250, 220);

            GameObject qstTitleObj = new GameObject("Title");
            qstTitleObj.transform.SetParent(questPanel.transform, false);
            questTitleText = qstTitleObj.AddComponent<Text>();
            questTitleText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            questTitleText.fontSize = 13;
            questTitleText.color = new Color(0.9f, 0.6f, 0f, 1f); // amber accent
            questTitleText.alignment = TextAnchor.UpperLeft;
            RectTransform qstTitleRect = questTitleText.GetComponent<RectTransform>();
            qstTitleRect.anchorMin = new Vector2(0, 1);
            qstTitleRect.anchorMax = new Vector2(1, 1);
            qstTitleRect.pivot = new Vector2(0, 1);
            qstTitleRect.anchoredPosition = new Vector2(15, -15);
            qstTitleRect.sizeDelta = new Vector2(-30, 20);

            GameObject qstDescObj = new GameObject("Description");
            qstDescObj.transform.SetParent(questPanel.transform, false);
            questDescText = qstDescObj.AddComponent<Text>();
            questDescText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            questDescText.fontSize = 11;
            questDescText.color = Color.white;
            questDescText.alignment = TextAnchor.UpperLeft;
            RectTransform qstDescRect = questDescText.GetComponent<RectTransform>();
            qstDescRect.anchorMin = new Vector2(0, 0);
            qstDescRect.anchorMax = new Vector2(1, 1);
            qstDescRect.offsetMin = new Vector2(15, 55);
            qstDescRect.offsetMax = new Vector2(-15, -45);

            GameObject acceptQstObj = new GameObject("AcceptButton");
            acceptQstObj.transform.SetParent(questPanel.transform, false);
            acceptQuestButton = acceptQstObj.AddComponent<Button>();
            Image accImg = acceptQstObj.AddComponent<Image>();
            accImg.color = new Color(0.2f, 0.4f, 0.2f, 0.9f); // green highlight
            GameObject accTextObj = new GameObject("Text");
            accTextObj.transform.SetParent(acceptQstObj.transform, false);
            Text accText = accTextObj.AddComponent<Text>();
            accText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            accText.text = "ACCEPT QUEST";
            accText.fontSize = 10;
            accText.alignment = TextAnchor.MiddleCenter;
            accText.color = Color.white;
            RectTransform accRect = acceptQstObj.GetComponent<RectTransform>();
            accRect.anchorMin = new Vector2(0.5f, 0);
            accRect.anchorMax = new Vector2(0.5f, 0);
            accRect.pivot = new Vector2(0.5f, 0);
            accRect.anchoredPosition = new Vector2(0, 15);
            accRect.sizeDelta = new Vector2(120, 30);
            acceptQuestButton.onClick.AddListener(AcceptQuest);
            questPanel.SetActive(false);

            // 5. Hint Panel (right overlay)
            hintPanel = new GameObject("HintPanel");
            hintPanel.transform.SetParent(canvasObj.transform, false);
            Image hntBg = hintPanel.AddComponent<Image>();
            hntBg.color = new Color(0.1f, 0.1f, 0.1f, 0.95f);
            RectTransform hntRect = hintPanel.GetComponent<RectTransform>();
            hntRect.anchorMin = new Vector2(1, 0.5f);
            hntRect.anchorMax = new Vector2(1, 0.5f);
            hntRect.pivot = new Vector2(1, 0.5f);
            hntRect.anchoredPosition = new Vector2(-30, 0);
            hntRect.sizeDelta = new Vector2(250, 220);

            GameObject hntTitleObj = new GameObject("Title");
            hntTitleObj.transform.SetParent(hintPanel.transform, false);
            Text hntTitleText = hntTitleObj.AddComponent<Text>();
            hntTitleText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            hntTitleText.fontSize = 13;
            hntTitleText.color = new Color(0f, 0.6f, 0.9f, 1f); // blue accent
            hntTitleText.text = "Quest Hint Engine";
            hntTitleText.alignment = TextAnchor.UpperLeft;
            RectTransform hntTitleRect = hntTitleText.GetComponent<RectTransform>();
            hntTitleRect.anchorMin = new Vector2(0, 1);
            hntTitleRect.anchorMax = new Vector2(1, 1);
            hntTitleRect.pivot = new Vector2(0, 1);
            hntTitleRect.anchoredPosition = new Vector2(15, -15);
            hntTitleRect.sizeDelta = new Vector2(-30, 20);

            GameObject hntBodyObj = new GameObject("HintText");
            hntBodyObj.transform.SetParent(hintPanel.transform, false);
            hintText = hntBodyObj.AddComponent<Text>();
            hintText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            hintText.fontSize = 11;
            hintText.color = Color.white;
            hintText.alignment = TextAnchor.UpperLeft;
            RectTransform hntBodyRect = hintText.GetComponent<RectTransform>();
            hntBodyRect.anchorMin = new Vector2(0, 0);
            hntBodyRect.anchorMax = new Vector2(1, 1);
            hntBodyRect.offsetMin = new Vector2(15, 55);
            hntBodyRect.offsetMax = new Vector2(-15, -45);

            GameObject reqHntObj = new GameObject("RequestButton");
            reqHntObj.transform.SetParent(hintPanel.transform, false);
            requestHintButton = reqHntObj.AddComponent<Button>();
            Image reqImg = reqHntObj.AddComponent<Image>();
            reqImg.color = new Color(0.2f, 0.2f, 0.4f, 0.9f); // blue highlight
            GameObject reqTextObj = new GameObject("Text");
            reqTextObj.transform.SetParent(reqHntObj.transform, false);
            Text reqText = reqTextObj.AddComponent<Text>();
            reqText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            reqText.text = "Request Hint";
            reqText.fontSize = 10;
            reqText.alignment = TextAnchor.MiddleCenter;
            reqText.color = Color.white;
            RectTransform reqRect = reqHntObj.GetComponent<RectTransform>();
            reqRect.anchorMin = new Vector2(0.5f, 0);
            reqRect.anchorMax = new Vector2(0.5f, 0);
            reqRect.pivot = new Vector2(0.5f, 0);
            reqRect.anchoredPosition = new Vector2(0, 15);
            reqRect.sizeDelta = new Vector2(120, 30);
            requestHintButton.onClick.AddListener(RequestHint);
            hintPanel.SetActive(false); // Locked until quest is accepted!
        }
    }
}
