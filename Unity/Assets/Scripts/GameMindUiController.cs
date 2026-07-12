using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using GameMind.Contracts;

namespace GameMind
{
    public class GameMindUiController : MonoBehaviour
    {
        [SerializeField] private bool useLatestRuntimeBundle = true;
        [SerializeField] private string targetBlueprintId = "00000000-0000-0000-0000-000000000000";

        private static readonly Color Surface = new Color(0.025f, 0.03f, 0.034f, 0.96f);
        private static readonly Color SurfaceSoft = new Color(0.055f, 0.06f, 0.066f, 0.94f);
        private static readonly Color SurfaceLine = new Color(0.18f, 0.22f, 0.25f, 0.86f);
        private static readonly Color TextPrimary = new Color(0.98f, 0.985f, 0.99f, 1f);
        private static readonly Color TextSecondary = new Color(0.75f, 0.80f, 0.86f, 1f);
        private static readonly Color Accent = new Color(0.58f, 0.86f, 0.94f, 1f);
        private static readonly Color Success = new Color(0.45f, 0.95f, 0.68f, 1f);
        private static readonly Color Warning = new Color(0.95f, 0.78f, 0.38f, 1f);
        private static readonly Color Danger = new Color(0.95f, 0.38f, 0.43f, 1f);
        private static readonly Color StageFloor = new Color(0.16f, 0.18f, 0.18f, 1f);
        private static readonly Color StageIce = new Color(0.42f, 0.70f, 0.78f, 1f);
        private static readonly Color StageStone = new Color(0.24f, 0.26f, 0.28f, 1f);
        private static readonly Color StageOre = new Color(0.30f, 0.78f, 0.92f, 1f);
        private static readonly Color StageFlag = new Color(0.25f, 0.90f, 0.52f, 1f);
        private static readonly Color StageAccent = new Color(0.30f, 0.58f, 0.64f, 1f);

        private readonly List<NpcProfileDto> materializedNpcs = new List<NpcProfileDto>();
        private readonly List<QuestDto> materializedQuests = new List<QuestDto>();

        private string activeQuestId = "";
        private int currentHintLevel = 1;

        private GameObject emptyStatePanel;
        private Text emptyTitleText;
        private Text emptyBodyText;
        private Button retryButton;
        private Text retryButtonText;

        private Text statusText;
        private Image statusDot;
        private Text keyboardHintText;

        private Button interactButton;
        private Text interactButtonText;

        private GameObject dialoguePanel;
        private Text dialogueSpeakerText;
        private Text dialogueText;
        private Button closeDialogueButton;

        private GameObject questPanel;
        private Text questTitleText;
        private Text questDescText;
        private Button acceptQuestButton;
        private Text acceptQuestButtonText;

        private GameObject hintPanel;
        private Text hintText;
        private Button requestHintButton;
        private Text requestHintButtonText;

        private NpcInteractionController eldrinController;

        private void Start()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;

            PrepareScenePresentation();
            eldrinController = FindFirstObjectByType<NpcInteractionController>();

            CreateCanvasUI();
            StartCoroutine(ConnectToBackend());
        }

        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.Escape) && dialoguePanel != null && dialoguePanel.activeSelf)
            {
                CloseDialogue();
            }

            if (Input.GetKeyDown(KeyCode.R))
            {
                StartCoroutine(ConnectToBackend());
            }

            if (Input.GetKeyDown(KeyCode.T) && interactButton != null && interactButton.gameObject.activeInHierarchy && interactButton.interactable)
            {
                InteractWithEldrin();
            }

            if (Input.GetKeyDown(KeyCode.A) && acceptQuestButton != null && acceptQuestButton.gameObject.activeInHierarchy && acceptQuestButton.interactable)
            {
                AcceptQuest();
            }

            if (Input.GetKeyDown(KeyCode.H) && requestHintButton != null && requestHintButton.gameObject.activeInHierarchy && requestHintButton.interactable)
            {
                RequestHint();
            }
        }

        private IEnumerator ConnectToBackend()
        {
            SetStatus("Connecting", Warning);
            if (retryButton != null)
            {
                retryButton.interactable = false;
                retryButtonText.text = "Checking...";
            }
            ShowEmptyState(
                "Loading runtime bundle",
                "Checking the latest materialized blueprint for this project. Press R to retry at any time."
            );

            yield return null;

            if (GameMindApiClient.Instance == null)
            {
                SetStatus("API client missing", Danger);
                ShowEmptyState(
                    "Unity client is not configured",
                    "Add GameMindApiClient to the GameMindManager object, then press Play again."
                );
                yield break;
            }

            yield return GameMindApiClient.Instance.GetRuntimeBundle(
                useLatestRuntimeBundle ? "" : targetBlueprintId,
                OnBundleLoaded,
                OnBundleError
            );
        }

        private void OnBundleLoaded(BlueprintRuntimeBundleResponse bundle)
        {
            materializedNpcs.Clear();
            materializedQuests.Clear();

            if (bundle != null)
            {
                if (bundle.npcs != null) materializedNpcs.AddRange(bundle.npcs);
                if (bundle.quests != null) materializedQuests.AddRange(bundle.quests);
            }

            if (materializedNpcs.Count == 0 && materializedQuests.Count == 0)
            {
                SetStatus("No runtime data", Warning);
                ShowEmptyState(
                    "No materialized blueprint found",
                    "In the dashboard: open Sources, load the Frostpeak demo, open Blueprints, generate, approve, and materialize. Then press R here to reload the latest runtime bundle."
                );
                interactButton.gameObject.SetActive(false);
                questPanel.SetActive(false);
                hintPanel.SetActive(false);
                SetRetryEnabled(true);
                return;
            }

            SetStatus("Runtime ready", Success);
            emptyStatePanel.SetActive(false);
            SetRetryEnabled(true);

            interactButton.gameObject.SetActive(materializedNpcs.Count > 0);
            interactButton.interactable = materializedNpcs.Count > 0;
            interactButtonText.text = materializedNpcs.Count > 0 ? $"Talk to {GetPreferredNpcName()}  T" : "No NPCs loaded";

            if (materializedQuests.Count > 0)
            {
                QuestDto quest = materializedQuests[0];
                activeQuestId = quest.id;
                questTitleText.text = quest.title;
                questDescText.text = $"{quest.description}\n\nReward: {quest.gold_reward} gold, {quest.xp_reward} XP";
                questPanel.SetActive(true);
                acceptQuestButton.gameObject.SetActive(true);
                acceptQuestButton.interactable = true;
                acceptQuestButtonText.text = "Accept quest";
            }
            else
            {
                questPanel.SetActive(false);
            }
        }

        private void OnBundleError(ErrorEnvelope error)
        {
            string message = GetErrorMessage(error, "The backend did not return a usable runtime bundle.");

            SetStatus("Connection error", Danger);
            ShowEmptyState("Could not load runtime", message);
            SetRetryEnabled(true);
            Debug.LogError($"[GameMind UI] Connection failed: {message}");
        }

        private void OnRuntimeActionError(string actionName, ErrorEnvelope error)
        {
            string message = GetErrorMessage(error, "The backend rejected this runtime action.");

            if (emptyStatePanel != null && (materializedNpcs.Count > 0 || materializedQuests.Count > 0))
            {
                emptyStatePanel.SetActive(false);
            }

            SetStatus($"{actionName} failed", Danger);
            if (keyboardHintText != null)
            {
                keyboardHintText.text = $"Last issue: {message}   R Reload";
            }

            Debug.LogWarning($"[GameMind UI] {actionName} failed: {message}");
        }

        private string GetErrorMessage(ErrorEnvelope error, string fallback)
        {
            if (error == null) return fallback;
            if (error.error != null && !string.IsNullOrEmpty(error.error.message)) return error.error.message;
            if (!string.IsNullOrEmpty(error.detail)) return error.detail;
            if (!string.IsNullOrEmpty(error.raw_message)) return error.raw_message;
            return fallback;
        }

        private bool IsAlreadyAcceptedQuest(ErrorEnvelope error)
        {
            string message = GetErrorMessage(error, "");
            return message.ToLower().Contains("already accepted") || message.ToLower().Contains("already accepted or completed");
        }

        private void InteractWithEldrin()
        {
            if (materializedNpcs.Count == 0)
            {
                ShowEmptyState("No NPC loaded", "Materialize a blueprint with at least one NPC before testing dialogue.");
                return;
            }

            string npcSlug = materializedNpcs[0].slug;
            string npcName = string.IsNullOrEmpty(materializedNpcs[0].name) ? "Eldrin" : materializedNpcs[0].name;
            foreach (NpcProfileDto npc in materializedNpcs)
            {
                if (!string.IsNullOrEmpty(npc.slug) && npc.slug.ToLower().Contains("eldrin"))
                {
                    npcSlug = npc.slug;
                    npcName = string.IsNullOrEmpty(npc.name) ? "Eldrin" : npc.name;
                    break;
                }
            }

            SetStatus($"Asking {npcName}", Warning);
            interactButton.interactable = false;
            interactButtonText.text = "Listening...";

            StartCoroutine(GameMindApiClient.Instance.SendChatDialogue(
                npcSlug,
                "Who is King Arven?",
                null,
                response =>
                {
                    SetStatus("Runtime ready", Success);
                    interactButton.interactable = true;
                    interactButtonText.text = $"Talk to {npcName}  T";

                    dialogueSpeakerText.text = npcName;
                    dialogueText.text = FormatDialogueText(response.response_text, npcName);
                    dialoguePanel.SetActive(true);

                    if (eldrinController != null)
                    {
                        eldrinController.HandleDialogueResponse(response);
                    }
                },
                error =>
                {
                    interactButton.interactable = true;
                    interactButtonText.text = $"Talk to {npcName}  T";
                    OnRuntimeActionError("Dialogue", error);
                }
            ));
        }

        private void AcceptQuest()
        {
            if (string.IsNullOrEmpty(activeQuestId))
            {
                SetStatus("No active quest", Warning);
                return;
            }

            SetStatus("Accepting quest", Warning);
            acceptQuestButton.interactable = false;
            acceptQuestButtonText.text = "Accepting...";

            StartCoroutine(GameMindApiClient.Instance.AcceptQuest(
                activeQuestId,
                response =>
                {
                    SetStatus("Quest accepted", Success);
                    acceptQuestButton.gameObject.SetActive(false);
                    hintPanel.SetActive(true);
                    hintText.text = "Quest accepted. Ask for progressive guidance when the player needs help.";
                },
                error =>
                {
                    if (IsAlreadyAcceptedQuest(error))
                    {
                        SetStatus("Quest already active", Success);
                        acceptQuestButton.gameObject.SetActive(false);
                        hintPanel.SetActive(true);
                        hintText.text = "Quest is already active for this player. You can request the next progressive hint.";
                        return;
                    }

                    acceptQuestButton.interactable = true;
                    acceptQuestButtonText.text = "Accept quest";
                    OnRuntimeActionError("Quest accept", error);
                }
            ));
        }

        private void RequestHint()
        {
            if (string.IsNullOrEmpty(activeQuestId))
            {
                SetStatus("No active quest", Warning);
                return;
            }

            SetStatus($"Hint level {currentHintLevel}", Warning);
            requestHintButton.interactable = false;
            requestHintButtonText.text = "Loading...";

            StartCoroutine(GameMindApiClient.Instance.GenerateHint(
                activeQuestId,
                currentHintLevel,
                response =>
                {
                    SetStatus("Runtime ready", Success);
                    hintText.text = $"Level {response.hint_level}: {response.hint}";
                    currentHintLevel = currentHintLevel >= 3 ? 1 : currentHintLevel + 1;
                    StartCoroutine(HintCooldownTimer(5));
                },
                error =>
                {
                    requestHintButton.interactable = true;
                    requestHintButtonText.text = "Request hint";
                    OnRuntimeActionError("Hint", error);
                    hintText.text = GetErrorMessage(error, "Hint could not be generated. Try again after reloading the runtime.");
                }
            ));
        }

        private IEnumerator HintCooldownTimer(int seconds)
        {
            for (int i = seconds; i > 0; i--)
            {
                requestHintButtonText.text = $"Cooldown {i}s";
                yield return new WaitForSeconds(1f);
            }

            requestHintButton.interactable = true;
            requestHintButtonText.text = "Request hint  H";
        }

        private void CloseDialogue()
        {
            dialoguePanel.SetActive(false);
        }

        private string FormatDialogueText(string rawText, string speakerName)
        {
            if (string.IsNullOrWhiteSpace(rawText)) return "No dialogue text was returned.";

            string cleaned = rawText.Trim();
            string prefix = $"{speakerName}:";
            if (cleaned.StartsWith(prefix, System.StringComparison.OrdinalIgnoreCase))
            {
                cleaned = cleaned.Substring(prefix.Length).Trim();
            }

            return cleaned;
        }

        private string GetPreferredNpcName()
        {
            if (materializedNpcs.Count == 0) return "NPC";

            foreach (NpcProfileDto npc in materializedNpcs)
            {
                if (!string.IsNullOrEmpty(npc.slug) && npc.slug.ToLower().Contains("eldrin"))
                {
                    return string.IsNullOrEmpty(npc.name) ? "Eldrin" : npc.name;
                }
            }

            return string.IsNullOrEmpty(materializedNpcs[0].name) ? "NPC" : materializedNpcs[0].name;
        }

        private void CreateCanvasUI()
        {
            EnsureEventSystem();

            GameObject canvasObj = new GameObject("GameMindCanvas");
            Canvas canvas = canvasObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;

            CanvasScaler scaler = canvasObj.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1440, 900);
            scaler.matchWidthOrHeight = 0.5f;

            canvasObj.AddComponent<GraphicRaycaster>();

            CreateStatusBadge(canvasObj.transform);
            CreateEmptyState(canvasObj.transform);
            CreateInteractButton(canvasObj.transform);
            CreateQuestPanel(canvasObj.transform);
            CreateHintPanel(canvasObj.transform);
            CreateDialoguePanel(canvasObj.transform);
            CreateKeyboardHint(canvasObj.transform);
        }

        private void CreateStatusBadge(Transform parent)
        {
            GameObject badge = CreatePanel("StatusBadge", parent, new Color(0.03f, 0.035f, 0.04f, 0.78f), true);
            RectTransform rect = badge.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(1f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.pivot = new Vector2(1f, 1f);
            rect.anchoredPosition = new Vector2(-28f, -28f);
            rect.sizeDelta = new Vector2(210f, 44f);

            GameObject dotObj = new GameObject("StatusDot");
            dotObj.transform.SetParent(badge.transform, false);
            statusDot = dotObj.AddComponent<Image>();
            statusDot.color = Warning;
            statusDot.raycastTarget = false;
            RectTransform dotRect = statusDot.GetComponent<RectTransform>();
            dotRect.anchorMin = new Vector2(0f, 0.5f);
            dotRect.anchorMax = new Vector2(0f, 0.5f);
            dotRect.pivot = new Vector2(0f, 0.5f);
            dotRect.anchoredPosition = new Vector2(18f, 0f);
            dotRect.sizeDelta = new Vector2(8f, 8f);

            statusText = CreateText("StatusText", badge.transform, "Connecting", 14, TextPrimary, TextAnchor.MiddleLeft);
            RectTransform textRect = statusText.GetComponent<RectTransform>();
            textRect.anchorMin = new Vector2(0f, 0f);
            textRect.anchorMax = new Vector2(1f, 1f);
            textRect.offsetMin = new Vector2(34f, 0f);
            textRect.offsetMax = new Vector2(-12f, 0f);
        }

        private void CreateEmptyState(Transform parent)
        {
            emptyStatePanel = CreatePanel("EmptyState", parent, Surface, false);
            RectTransform rect = emptyStatePanel.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.5f, 0.5f);
            rect.anchorMax = new Vector2(0.5f, 0.5f);
            rect.pivot = new Vector2(0.5f, 0.5f);
            rect.anchoredPosition = Vector2.zero;
            rect.sizeDelta = new Vector2(560f, 300f);

            Text eyebrow = CreateText("Eyebrow", emptyStatePanel.transform, "GAMEMIND RUNTIME", 11, Accent, TextAnchor.UpperLeft);
            RectTransform eyebrowRect = eyebrow.GetComponent<RectTransform>();
            eyebrowRect.anchorMin = new Vector2(0f, 1f);
            eyebrowRect.anchorMax = new Vector2(1f, 1f);
            eyebrowRect.pivot = new Vector2(0f, 1f);
            eyebrowRect.anchoredPosition = new Vector2(34f, -30f);
            eyebrowRect.sizeDelta = new Vector2(-68f, 22f);

            emptyTitleText = CreateText("Title", emptyStatePanel.transform, "Loading runtime bundle", 26, TextPrimary, TextAnchor.UpperLeft);
            RectTransform titleRect = emptyTitleText.GetComponent<RectTransform>();
            titleRect.anchorMin = new Vector2(0f, 1f);
            titleRect.anchorMax = new Vector2(1f, 1f);
            titleRect.pivot = new Vector2(0f, 1f);
            titleRect.anchoredPosition = new Vector2(34f, -64f);
            titleRect.sizeDelta = new Vector2(-68f, 40f);

            emptyBodyText = CreateText("Body", emptyStatePanel.transform, "", 14, TextSecondary, TextAnchor.UpperLeft);
            RectTransform bodyRect = emptyBodyText.GetComponent<RectTransform>();
            bodyRect.anchorMin = new Vector2(0f, 0f);
            bodyRect.anchorMax = new Vector2(1f, 1f);
            bodyRect.offsetMin = new Vector2(34f, 86f);
            bodyRect.offsetMax = new Vector2(-34f, -118f);

            retryButton = CreateButton("RetryButton", emptyStatePanel.transform, "Retry runtime load  R", Accent, new Color(0.03f, 0.05f, 0.06f, 1f), out retryButtonText);
            RectTransform retryRect = retryButton.GetComponent<RectTransform>();
            retryRect.anchorMin = new Vector2(0f, 0f);
            retryRect.anchorMax = new Vector2(1f, 0f);
            retryRect.pivot = new Vector2(0.5f, 0f);
            retryRect.offsetMin = new Vector2(34f, 30f);
            retryRect.offsetMax = new Vector2(-34f, 78f);
            retryButton.onClick.AddListener(() =>
            {
                Debug.Log("[GameMind UI] Retry runtime load clicked.");
                StartCoroutine(ConnectToBackend());
            });
        }

        private void CreateInteractButton(Transform parent)
        {
            interactButton = CreateButton("InteractButton", parent, "Talk to Eldrin  T", Accent, new Color(0.03f, 0.05f, 0.06f, 1f), out interactButtonText);
            RectTransform rect = interactButton.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.5f, 0f);
            rect.anchorMax = new Vector2(0.5f, 0f);
            rect.pivot = new Vector2(0.5f, 0f);
            rect.anchoredPosition = new Vector2(0f, 34f);
            rect.sizeDelta = new Vector2(280f, 62f);
            interactButton.onClick.AddListener(() =>
            {
                Debug.Log("[GameMind UI] Talk button clicked.");
                InteractWithEldrin();
            });
            interactButton.gameObject.SetActive(false);
        }

        private void CreateQuestPanel(Transform parent)
        {
            questPanel = CreatePanel("QuestPanel", parent, Surface, false);
            RectTransform rect = questPanel.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(1f, 0.5f);
            rect.anchorMax = new Vector2(1f, 0.5f);
            rect.pivot = new Vector2(1f, 0.5f);
            rect.anchoredPosition = new Vector2(-36f, 24f);
            rect.sizeDelta = new Vector2(420f, 330f);

            Text label = CreateText("Label", questPanel.transform, "ACTIVE QUEST", 12, Accent, TextAnchor.UpperLeft);
            SetRect(label.rectTransform, new Vector2(24f, -24f), new Vector2(-48f, 24f), true);

            questTitleText = CreateText("QuestTitle", questPanel.transform, "Quest title", 23, TextPrimary, TextAnchor.UpperLeft);
            SetRect(questTitleText.rectTransform, new Vector2(24f, -60f), new Vector2(-48f, 44f), true);

            questDescText = CreateText("QuestDescription", questPanel.transform, "", 15, TextSecondary, TextAnchor.UpperLeft);
            RectTransform descRect = questDescText.GetComponent<RectTransform>();
            descRect.anchorMin = new Vector2(0f, 0f);
            descRect.anchorMax = new Vector2(1f, 1f);
            descRect.offsetMin = new Vector2(24f, 92f);
            descRect.offsetMax = new Vector2(-24f, -108f);

            acceptQuestButton = CreateButton("AcceptQuestButton", questPanel.transform, "Accept quest  A", Success, new Color(0.03f, 0.08f, 0.05f, 1f), out acceptQuestButtonText);
            RectTransform buttonRect = acceptQuestButton.GetComponent<RectTransform>();
            buttonRect.anchorMin = new Vector2(0f, 0f);
            buttonRect.anchorMax = new Vector2(1f, 0f);
            buttonRect.pivot = new Vector2(0.5f, 0f);
            buttonRect.offsetMin = new Vector2(24f, 24f);
            buttonRect.offsetMax = new Vector2(-24f, 72f);
            acceptQuestButton.onClick.AddListener(() =>
            {
                Debug.Log("[GameMind UI] Accept quest clicked.");
                AcceptQuest();
            });

            questPanel.SetActive(false);
        }

        private void CreateHintPanel(Transform parent)
        {
            hintPanel = CreatePanel("HintPanel", parent, SurfaceSoft, false);
            RectTransform rect = hintPanel.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(1f, 0.5f);
            rect.anchorMax = new Vector2(1f, 0.5f);
            rect.pivot = new Vector2(1f, 0.5f);
            rect.anchoredPosition = new Vector2(-36f, -200f);
            rect.sizeDelta = new Vector2(420f, 178f);

            Text label = CreateText("Label", hintPanel.transform, "PROGRESSIVE HINT", 12, Accent, TextAnchor.UpperLeft);
            SetRect(label.rectTransform, new Vector2(24f, -22f), new Vector2(-48f, 24f), true);

            hintText = CreateText("HintText", hintPanel.transform, "Accept the quest to unlock contextual hints.", 15, TextSecondary, TextAnchor.UpperLeft);
            RectTransform hintRect = hintText.GetComponent<RectTransform>();
            hintRect.anchorMin = new Vector2(0f, 0f);
            hintRect.anchorMax = new Vector2(1f, 1f);
            hintRect.offsetMin = new Vector2(24f, 64f);
            hintRect.offsetMax = new Vector2(-24f, -58f);

            requestHintButton = CreateButton("RequestHintButton", hintPanel.transform, "Request hint  H", Accent, new Color(0.03f, 0.06f, 0.08f, 1f), out requestHintButtonText);
            RectTransform buttonRect = requestHintButton.GetComponent<RectTransform>();
            buttonRect.anchorMin = new Vector2(0f, 0f);
            buttonRect.anchorMax = new Vector2(1f, 0f);
            buttonRect.pivot = new Vector2(0.5f, 0f);
            buttonRect.offsetMin = new Vector2(24f, 18f);
            buttonRect.offsetMax = new Vector2(-24f, 58f);
            requestHintButton.onClick.AddListener(() =>
            {
                Debug.Log("[GameMind UI] Request hint clicked.");
                RequestHint();
            });

            hintPanel.SetActive(false);
        }

        private void CreateDialoguePanel(Transform parent)
        {
            dialoguePanel = CreatePanel("DialoguePanel", parent, Surface, false);
            RectTransform rect = dialoguePanel.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.5f, 0f);
            rect.anchorMax = new Vector2(0.5f, 0f);
            rect.pivot = new Vector2(0.5f, 0f);
            rect.anchoredPosition = new Vector2(0f, 126f);
            rect.sizeDelta = new Vector2(840f, 220f);

            dialogueSpeakerText = CreateText("Speaker", dialoguePanel.transform, "Eldrin", 13, Accent, TextAnchor.UpperLeft);
            SetRect(dialogueSpeakerText.rectTransform, new Vector2(32f, -28f), new Vector2(-150f, 26f), true);

            dialogueText = CreateText("DialogueText", dialoguePanel.transform, "", 18, TextPrimary, TextAnchor.UpperLeft);
            RectTransform dialogueRect = dialogueText.GetComponent<RectTransform>();
            dialogueRect.anchorMin = new Vector2(0f, 0f);
            dialogueRect.anchorMax = new Vector2(1f, 1f);
            dialogueRect.offsetMin = new Vector2(32f, 32f);
            dialogueRect.offsetMax = new Vector2(-32f, -70f);

            closeDialogueButton = CreateButton("CloseDialogueButton", dialoguePanel.transform, "Close", SurfaceLine, TextPrimary, out _);
            RectTransform closeRect = closeDialogueButton.GetComponent<RectTransform>();
            closeRect.anchorMin = new Vector2(1f, 1f);
            closeRect.anchorMax = new Vector2(1f, 1f);
            closeRect.pivot = new Vector2(1f, 1f);
            closeRect.anchoredPosition = new Vector2(-28f, -22f);
            closeRect.sizeDelta = new Vector2(96f, 40f);
            closeDialogueButton.onClick.AddListener(() =>
            {
                Debug.Log("[GameMind UI] Close dialogue clicked.");
                CloseDialogue();
            });

            dialoguePanel.SetActive(false);
        }

        private void CreateKeyboardHint(Transform parent)
        {
            GameObject panel = CreatePanel("KeyboardHint", parent, new Color(0.03f, 0.035f, 0.04f, 0.68f), false);
            RectTransform rect = panel.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 0f);
            rect.anchorMax = new Vector2(0f, 0f);
            rect.pivot = new Vector2(0f, 0f);
            rect.anchoredPosition = new Vector2(28f, 26f);
            rect.sizeDelta = new Vector2(520f, 42f);

            keyboardHintText = CreateText("KeyboardHintText", panel.transform, "T Talk   A Accept quest   H Hint   R Reload   Esc Close", 14, TextSecondary, TextAnchor.MiddleLeft);
            RectTransform textRect = keyboardHintText.GetComponent<RectTransform>();
            textRect.anchorMin = Vector2.zero;
            textRect.anchorMax = Vector2.one;
            textRect.offsetMin = new Vector2(16f, 0f);
            textRect.offsetMax = new Vector2(-16f, 0f);
        }

        private Button CreateButton(string name, Transform parent, string label, Color background, Color textColor, out Text labelText)
        {
            GameObject obj = new GameObject(name);
            obj.transform.SetParent(parent, false);

            Image image = obj.AddComponent<Image>();
            image.color = background;
            image.raycastTarget = true;

            Button button = obj.AddComponent<Button>();
            button.targetGraphic = image;
            button.transition = Selectable.Transition.ColorTint;
            button.colors = CreateButtonColors(background);

            labelText = CreateText("Label", obj.transform, label, 16, textColor, TextAnchor.MiddleCenter);
            labelText.fontStyle = FontStyle.Bold;
            RectTransform labelRect = labelText.GetComponent<RectTransform>();
            labelRect.anchorMin = Vector2.zero;
            labelRect.anchorMax = Vector2.one;
            labelRect.offsetMin = Vector2.zero;
            labelRect.offsetMax = Vector2.zero;

            return button;
        }

        private ColorBlock CreateButtonColors(Color normal)
        {
            ColorBlock colors = ColorBlock.defaultColorBlock;
            colors.normalColor = normal;
            colors.highlightedColor = Color.Lerp(normal, Color.white, 0.12f);
            colors.pressedColor = Color.Lerp(normal, Color.black, 0.16f);
            colors.selectedColor = colors.highlightedColor;
            colors.disabledColor = new Color(normal.r, normal.g, normal.b, 0.38f);
            colors.colorMultiplier = 1f;
            colors.fadeDuration = 0.12f;
            return colors;
        }

        private GameObject CreatePanel(string name, Transform parent, Color color, bool raycastTarget)
        {
            GameObject obj = new GameObject(name);
            obj.transform.SetParent(parent, false);
            Image image = obj.AddComponent<Image>();
            image.color = color;
            image.raycastTarget = raycastTarget;
            return obj;
        }

        private Text CreateText(string name, Transform parent, string content, int size, Color color, TextAnchor alignment)
        {
            GameObject obj = new GameObject(name);
            obj.transform.SetParent(parent, false);
            Text text = obj.AddComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.text = content;
            text.fontSize = size;
            text.color = color;
            text.alignment = alignment;
            text.lineSpacing = 1.18f;
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            text.verticalOverflow = VerticalWrapMode.Truncate;
            text.raycastTarget = false;
            return text;
        }

        private void SetRect(RectTransform rect, Vector2 anchoredPosition, Vector2 sizeDelta, bool topAnchored)
        {
            if (topAnchored)
            {
                rect.anchorMin = new Vector2(0f, 1f);
                rect.anchorMax = new Vector2(1f, 1f);
                rect.pivot = new Vector2(0f, 1f);
            }

            rect.anchoredPosition = anchoredPosition;
            rect.sizeDelta = sizeDelta;
        }

        private void SetStatus(string text, Color color)
        {
            statusText.text = text;
            statusDot.color = color;
        }

        private void ShowEmptyState(string title, string body)
        {
            emptyTitleText.text = title;
            emptyBodyText.text = body;
            emptyStatePanel.SetActive(true);
        }

        private void SetRetryEnabled(bool enabled)
        {
            if (retryButton == null || retryButtonText == null) return;
            retryButton.interactable = enabled;
            retryButtonText.text = enabled ? "Retry runtime load  R" : "Checking...";
        }

        private void PrepareScenePresentation()
        {
            Camera mainCamera = Camera.main;
            if (mainCamera != null)
            {
                mainCamera.transform.position = new Vector3(0f, 3.2f, -7.8f);
                mainCamera.transform.rotation = Quaternion.Euler(17f, 0f, 0f);
                mainCamera.clearFlags = CameraClearFlags.SolidColor;
                mainCamera.backgroundColor = new Color(0.08f, 0.095f, 0.11f, 1f);
                mainCamera.fieldOfView = 38f;
            }

            if (GameObject.Find("GameMindDemoFloor") == null)
            {
                GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
                floor.name = "GameMindDemoFloor";
                floor.transform.position = Vector3.zero;
                floor.transform.localScale = new Vector3(7.5f, 1f, 5.4f);
                SetMaterial(floor, StageFloor, 0.18f);
            }

            if (FindFirstObjectByType<NpcInteractionController>() == null)
            {
                GameObject npc = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                npc.name = "Runtime Eldrin Proxy";
                npc.transform.position = new Vector3(0f, 1.05f, 0.15f);
                npc.transform.localScale = new Vector3(0.78f, 1.18f, 0.78f);
                SetMaterial(npc, StageAccent, 0.22f);
                npc.AddComponent<Animator>();
                npc.AddComponent<NpcInteractionController>();
            }

            CreateFrostpeakSetDressing();

            if (FindFirstObjectByType<Light>() == null)
            {
                GameObject lightObj = new GameObject("GameMindKeyLight");
                Light light = lightObj.AddComponent<Light>();
                light.type = LightType.Directional;
                light.intensity = 1.45f;
                light.color = new Color(0.82f, 0.93f, 1f, 1f);
                light.transform.rotation = Quaternion.Euler(46f, -32f, 0f);
            }
        }

        private void CreateFrostpeakSetDressing()
        {
            if (GameObject.Find("GameMindFrostpeakSet") != null) return;

            GameObject root = new GameObject("GameMindFrostpeakSet");
            CreateProp(root.transform, "AshPassStoneLeft", PrimitiveType.Cube, new Vector3(-2.25f, 0.28f, 1.35f), new Vector3(0.45f, 0.56f, 1.15f), StageStone);
            CreateProp(root.transform, "AshPassStoneRight", PrimitiveType.Cube, new Vector3(2.25f, 0.28f, 1.35f), new Vector3(0.45f, 0.56f, 1.15f), StageStone);
            CreateProp(root.transform, "BrokenGateLintel", PrimitiveType.Cube, new Vector3(0f, 1.05f, 1.42f), new Vector3(4.8f, 0.22f, 0.18f), StageStone);

            CreateProp(root.transform, "SkyIronOreA", PrimitiveType.Sphere, new Vector3(-1.55f, 0.2f, -0.75f), new Vector3(0.34f, 0.18f, 0.34f), StageOre);
            CreateProp(root.transform, "SkyIronOreB", PrimitiveType.Sphere, new Vector3(1.6f, 0.18f, -0.9f), new Vector3(0.28f, 0.14f, 0.28f), StageOre);
            CreateProp(root.transform, "FrostPatchA", PrimitiveType.Cube, new Vector3(-0.95f, 0.015f, -0.25f), new Vector3(1.6f, 0.03f, 0.55f), StageIce);
            CreateProp(root.transform, "FrostPatchB", PrimitiveType.Cube, new Vector3(1.05f, 0.015f, 0.65f), new Vector3(1.2f, 0.03f, 0.42f), StageIce);

            GameObject flagPole = CreateProp(root.transform, "NorthernFlagPole", PrimitiveType.Cylinder, new Vector3(-2.65f, 0.78f, -0.05f), new Vector3(0.045f, 0.78f, 0.045f), StageStone);
            flagPole.transform.rotation = Quaternion.Euler(0f, 0f, 0f);
            CreateProp(root.transform, "NorthernFlag", PrimitiveType.Cube, new Vector3(-2.36f, 1.28f, -0.05f), new Vector3(0.56f, 0.28f, 0.035f), StageFlag);
        }

        private GameObject CreateProp(Transform parent, string name, PrimitiveType primitive, Vector3 position, Vector3 scale, Color color)
        {
            GameObject prop = GameObject.CreatePrimitive(primitive);
            prop.name = name;
            prop.transform.SetParent(parent, false);
            prop.transform.position = position;
            prop.transform.localScale = scale;
            SetMaterial(prop, color, 0.12f);
            return prop;
        }

        private void SetMaterial(GameObject obj, Color color, float smoothness)
        {
            Renderer renderer = obj.GetComponent<Renderer>();
            if (renderer == null) return;

            Material material = new Material(Shader.Find("Standard"));
            material.color = color;
            material.SetFloat("_Glossiness", smoothness);
            renderer.material = material;
        }

        private void EnsureEventSystem()
        {
            EventSystem existingEventSystem = FindFirstObjectByType<EventSystem>();
            if (existingEventSystem != null)
            {
                if (existingEventSystem.GetComponent<BaseInputModule>() == null)
                {
                    existingEventSystem.gameObject.AddComponent<StandaloneInputModule>();
                }
                return;
            }

            GameObject eventSystemObj = new GameObject("EventSystem");
            eventSystemObj.AddComponent<EventSystem>();
            eventSystemObj.AddComponent<StandaloneInputModule>();
        }
    }
}
