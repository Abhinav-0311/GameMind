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
        [SerializeField] private string targetBlueprintId = "00000000-0000-0000-0000-000000000000";

        private static readonly Color Surface = new Color(0.035f, 0.04f, 0.045f, 0.94f);
        private static readonly Color SurfaceSoft = new Color(0.07f, 0.075f, 0.08f, 0.92f);
        private static readonly Color SurfaceLine = new Color(0.24f, 0.26f, 0.28f, 0.7f);
        private static readonly Color TextPrimary = new Color(0.96f, 0.97f, 0.98f, 1f);
        private static readonly Color TextSecondary = new Color(0.67f, 0.72f, 0.78f, 1f);
        private static readonly Color Accent = new Color(0.58f, 0.86f, 0.94f, 1f);
        private static readonly Color Success = new Color(0.45f, 0.95f, 0.68f, 1f);
        private static readonly Color Warning = new Color(0.95f, 0.78f, 0.38f, 1f);
        private static readonly Color Danger = new Color(0.95f, 0.38f, 0.43f, 1f);

        private readonly List<NpcProfileDto> materializedNpcs = new List<NpcProfileDto>();
        private readonly List<QuestDto> materializedQuests = new List<QuestDto>();

        private string activeQuestId = "";
        private int currentHintLevel = 1;

        private GameObject emptyStatePanel;
        private Text emptyTitleText;
        private Text emptyBodyText;

        private Text statusText;
        private Image statusDot;

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

            eldrinController = FindFirstObjectByType<NpcInteractionController>();

            CreateCanvasUI();
            StartCoroutine(ConnectToBackend());
        }

        private IEnumerator ConnectToBackend()
        {
            SetStatus("Connecting", Warning);
            ShowEmptyState(
                "Loading runtime bundle",
                "GameMind is checking the approved blueprint and materialized gameplay data for this scene."
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
                targetBlueprintId,
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
                    "Approve and materialize a blueprint in the dashboard, then paste that blueprint ID into Target Blueprint Id."
                );
                interactButton.gameObject.SetActive(false);
                questPanel.SetActive(false);
                hintPanel.SetActive(false);
                return;
            }

            SetStatus("Runtime ready", Success);
            emptyStatePanel.SetActive(false);

            interactButton.gameObject.SetActive(materializedNpcs.Count > 0);
            interactButton.interactable = materializedNpcs.Count > 0;
            interactButtonText.text = materializedNpcs.Count > 0 ? "Talk to Eldrin" : "No NPCs loaded";

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
            string message = error != null && error.error != null
                ? error.error.message
                : "The backend did not return a usable runtime bundle.";

            SetStatus("Connection error", Danger);
            ShowEmptyState("Could not load runtime", message);
            Debug.LogError($"[GameMind UI] Connection failed: {message}");
        }

        private void InteractWithEldrin()
        {
            if (materializedNpcs.Count == 0)
            {
                ShowEmptyState("No NPC loaded", "Materialize a blueprint with at least one NPC before testing dialogue.");
                return;
            }

            string npcSlug = materializedNpcs[0].slug;
            foreach (NpcProfileDto npc in materializedNpcs)
            {
                if (!string.IsNullOrEmpty(npc.slug) && npc.slug.ToLower().Contains("eldrin"))
                {
                    npcSlug = npc.slug;
                    break;
                }
            }

            SetStatus("Asking Eldrin", Warning);
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
                    interactButtonText.text = "Talk to Eldrin";

                    dialogueSpeakerText.text = response.npc_slug;
                    dialogueText.text = response.response_text;
                    dialoguePanel.SetActive(true);

                    if (eldrinController != null)
                    {
                        eldrinController.HandleDialogueResponse(response);
                    }
                },
                error =>
                {
                    interactButton.interactable = true;
                    interactButtonText.text = "Talk to Eldrin";
                    OnBundleError(error);
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
                    hintText.text = "Quest accepted. Request a hint when the player needs guidance.";
                },
                error =>
                {
                    acceptQuestButton.interactable = true;
                    acceptQuestButtonText.text = "Accept quest";
                    OnBundleError(error);
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
                    OnBundleError(error);
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
            requestHintButtonText.text = "Request hint";
        }

        private void CloseDialogue()
        {
            dialoguePanel.SetActive(false);
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

            statusText = CreateText("StatusText", badge.transform, "Connecting", 13, TextPrimary, TextAnchor.MiddleLeft);
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
            rect.sizeDelta = new Vector2(520f, 230f);

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
            bodyRect.offsetMin = new Vector2(34f, 36f);
            bodyRect.offsetMax = new Vector2(-34f, -118f);
        }

        private void CreateInteractButton(Transform parent)
        {
            interactButton = CreateButton("InteractButton", parent, "Talk to Eldrin", Accent, new Color(0.03f, 0.05f, 0.06f, 1f), out interactButtonText);
            RectTransform rect = interactButton.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.5f, 0f);
            rect.anchorMax = new Vector2(0.5f, 0f);
            rect.pivot = new Vector2(0.5f, 0f);
            rect.anchoredPosition = new Vector2(0f, 36f);
            rect.sizeDelta = new Vector2(220f, 52f);
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
            rect.anchoredPosition = new Vector2(-32f, 20f);
            rect.sizeDelta = new Vector2(360f, 310f);

            Text label = CreateText("Label", questPanel.transform, "ACTIVE QUEST", 11, Accent, TextAnchor.UpperLeft);
            SetRect(label.rectTransform, new Vector2(24f, -24f), new Vector2(-48f, 24f), true);

            questTitleText = CreateText("QuestTitle", questPanel.transform, "Quest title", 20, TextPrimary, TextAnchor.UpperLeft);
            SetRect(questTitleText.rectTransform, new Vector2(24f, -58f), new Vector2(-48f, 34f), true);

            questDescText = CreateText("QuestDescription", questPanel.transform, "", 13, TextSecondary, TextAnchor.UpperLeft);
            RectTransform descRect = questDescText.GetComponent<RectTransform>();
            descRect.anchorMin = new Vector2(0f, 0f);
            descRect.anchorMax = new Vector2(1f, 1f);
            descRect.offsetMin = new Vector2(24f, 82f);
            descRect.offsetMax = new Vector2(-24f, -112f);

            acceptQuestButton = CreateButton("AcceptQuestButton", questPanel.transform, "Accept quest", Success, new Color(0.03f, 0.08f, 0.05f, 1f), out acceptQuestButtonText);
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
            rect.anchoredPosition = new Vector2(-32f, -170f);
            rect.sizeDelta = new Vector2(360f, 150f);

            Text label = CreateText("Label", hintPanel.transform, "PROGRESSIVE HINT", 11, Accent, TextAnchor.UpperLeft);
            SetRect(label.rectTransform, new Vector2(24f, -22f), new Vector2(-48f, 24f), true);

            hintText = CreateText("HintText", hintPanel.transform, "Accept the quest to unlock contextual hints.", 13, TextSecondary, TextAnchor.UpperLeft);
            RectTransform hintRect = hintText.GetComponent<RectTransform>();
            hintRect.anchorMin = new Vector2(0f, 0f);
            hintRect.anchorMax = new Vector2(1f, 1f);
            hintRect.offsetMin = new Vector2(24f, 56f);
            hintRect.offsetMax = new Vector2(-24f, -54f);

            requestHintButton = CreateButton("RequestHintButton", hintPanel.transform, "Request hint", Accent, new Color(0.03f, 0.06f, 0.08f, 1f), out requestHintButtonText);
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
            rect.anchoredPosition = new Vector2(0f, 112f);
            rect.sizeDelta = new Vector2(720f, 170f);

            dialogueSpeakerText = CreateText("Speaker", dialoguePanel.transform, "Eldrin", 12, Accent, TextAnchor.UpperLeft);
            SetRect(dialogueSpeakerText.rectTransform, new Vector2(28f, -24f), new Vector2(-140f, 24f), true);

            dialogueText = CreateText("DialogueText", dialoguePanel.transform, "", 15, TextPrimary, TextAnchor.UpperLeft);
            RectTransform dialogueRect = dialogueText.GetComponent<RectTransform>();
            dialogueRect.anchorMin = new Vector2(0f, 0f);
            dialogueRect.anchorMax = new Vector2(1f, 1f);
            dialogueRect.offsetMin = new Vector2(28f, 28f);
            dialogueRect.offsetMax = new Vector2(-28f, -58f);

            closeDialogueButton = CreateButton("CloseDialogueButton", dialoguePanel.transform, "Close", SurfaceLine, TextPrimary, out _);
            RectTransform closeRect = closeDialogueButton.GetComponent<RectTransform>();
            closeRect.anchorMin = new Vector2(1f, 1f);
            closeRect.anchorMax = new Vector2(1f, 1f);
            closeRect.pivot = new Vector2(1f, 1f);
            closeRect.anchoredPosition = new Vector2(-22f, -18f);
            closeRect.sizeDelta = new Vector2(84f, 36f);
            closeDialogueButton.onClick.AddListener(() =>
            {
                Debug.Log("[GameMind UI] Close dialogue clicked.");
                CloseDialogue();
            });

            dialoguePanel.SetActive(false);
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

            labelText = CreateText("Label", obj.transform, label, 14, textColor, TextAnchor.MiddleCenter);
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
