using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using GameMind.Contracts;

namespace GameMind
{
    public class GameMindApiClient : MonoBehaviour
    {
        [Serializable]
        private class ChatDialogueRequest
        {
            public string npc_slug;
            public string player_message;
            public string conversation_id;
        }

        [Serializable]
        private class GenerateQuestRequest
        {
            public string npc_slug;
            public int player_level;
        }

        [Serializable]
        private class AcceptQuestRequest
        {
            public string quest_id;
            public string player_id;
        }

        [Serializable]
        private class GenerateHintRequest
        {
            public string quest_id;
            public string player_id;
            public int hint_level;
        }

        public static GameMindApiClient Instance { get; private set; }

        [SerializeField] private string defaultProjectId = "default_project";
        [SerializeField] private string defaultPlayerId = "default_player";

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
            }
        }

        public IEnumerator SendChatDialogue(string npcSlug, string playerMessage, string conversationId, Action<DialogueChatResponse> onSuccess, Action<ErrorEnvelope> onError)
        {
            string url = $"{GameMindConfig.ApiBaseUrl}/api/v1/dialogue/chat";

            ChatDialogueRequest payload = new ChatDialogueRequest
            {
                npc_slug = npcSlug,
                player_message = playerMessage,
                conversation_id = conversationId
            };
            string jsonPayload = JsonUtility.ToJson(payload);

            using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.SetRequestHeader("X-Game-Project-ID", defaultProjectId);
                request.SetRequestHeader("X-Player-ID", defaultPlayerId);
                request.timeout = GameMindConfig.TimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.ProtocolError)
                {
                    HandleError(request, onError);
                }
                else
                {
                    try
                    {
                        string responseText = request.downloadHandler.text;
                        DialogueChatResponse response = JsonUtility.FromJson<DialogueChatResponse>(responseText);
                        
                        // API version validation
                        if (response.api_version != GameMindConfig.ApiVersion)
                        {
                            Debug.LogWarning($"API Version Mismatch! Client: {GameMindConfig.ApiVersion}, Server: {response.api_version}");
                        }
                        
                        onSuccess?.Invoke(response);
                    }
                    catch (Exception ex)
                    {
                        ErrorEnvelope parsingError = new ErrorEnvelope
                        {
                            api_version = GameMindConfig.ApiVersion,
                            error = new ErrorDetail { code = "PARSING_ERROR", message = $"Failed to parse response: {ex.Message}" }
                        };
                        onError?.Invoke(parsingError);
                    }
                }
            }
        }

        public IEnumerator GenerateQuest(string npcSlug, int playerLevel, Action<QuestGeneratedResponse> onSuccess, Action<ErrorEnvelope> onError)
        {
            string url = $"{GameMindConfig.ApiBaseUrl}/api/v1/quests/generate";
            string jsonPayload = JsonUtility.ToJson(new GenerateQuestRequest
            {
                npc_slug = npcSlug,
                player_level = playerLevel
            });

            using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.SetRequestHeader("X-Game-Project-ID", defaultProjectId);
                request.SetRequestHeader("X-Player-ID", defaultPlayerId);
                request.timeout = GameMindConfig.TimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.ProtocolError)
                {
                    HandleError(request, onError);
                }
                else
                {
                    try
                    {
                        string responseText = request.downloadHandler.text;
                        QuestGeneratedResponse response = JsonUtility.FromJson<QuestGeneratedResponse>(responseText);
                        
                        if (response.api_version != GameMindConfig.ApiVersion)
                        {
                            Debug.LogWarning($"API Version Mismatch! Client: {GameMindConfig.ApiVersion}, Server: {response.api_version}");
                        }
                        
                        onSuccess?.Invoke(response);
                    }
                    catch (Exception ex)
                    {
                        ErrorEnvelope parsingError = new ErrorEnvelope
                        {
                            api_version = GameMindConfig.ApiVersion,
                            error = new ErrorDetail { code = "PARSING_ERROR", message = $"Failed to parse response: {ex.Message}" }
                        };
                        onError?.Invoke(parsingError);
                    }
                }
            }
        }

        public IEnumerator GetRuntimeBundle(string blueprintId, Action<BlueprintRuntimeBundleResponse> onSuccess, Action<ErrorEnvelope> onError)
        {
            bool useLatestBundle = string.IsNullOrWhiteSpace(blueprintId) || blueprintId == "00000000-0000-0000-0000-000000000000";
            string url = useLatestBundle
                ? $"{GameMindConfig.ApiBaseUrl}/api/v1/blueprints/runtime/latest-bundle"
                : $"{GameMindConfig.ApiBaseUrl}/api/v1/blueprints/{blueprintId}/runtime-bundle";

            using (UnityWebRequest request = UnityWebRequest.Get(url))
            {
                request.SetRequestHeader("X-Game-Project-ID", defaultProjectId);
                request.timeout = GameMindConfig.TimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.ProtocolError)
                {
                    HandleError(request, onError);
                }
                else
                {
                    try
                    {
                        string responseText = request.downloadHandler.text;
                        BlueprintRuntimeBundleResponse response = JsonUtility.FromJson<BlueprintRuntimeBundleResponse>(responseText);
                        onSuccess?.Invoke(response);
                    }
                    catch (Exception ex)
                    {
                        ErrorEnvelope parsingError = new ErrorEnvelope
                        {
                            api_version = GameMindConfig.ApiVersion,
                            error = new ErrorDetail { code = "PARSING_ERROR", message = $"Failed to parse response: {ex.Message}" }
                        };
                        onError?.Invoke(parsingError);
                    }
                }
            }
        }

        public IEnumerator AcceptQuest(string questId, Action<QuestProgressResponse> onSuccess, Action<ErrorEnvelope> onError)
        {
            string url = $"{GameMindConfig.ApiBaseUrl}/api/v1/quests/progress";
            string jsonPayload = JsonUtility.ToJson(new AcceptQuestRequest
            {
                quest_id = questId,
                player_id = defaultPlayerId
            });

            using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.SetRequestHeader("X-Game-Project-ID", defaultProjectId);
                request.SetRequestHeader("X-Player-ID", defaultPlayerId);
                request.timeout = GameMindConfig.TimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.ProtocolError)
                {
                    HandleError(request, onError);
                }
                else
                {
                    try
                    {
                        string responseText = request.downloadHandler.text;
                        QuestProgressResponse response = JsonUtility.FromJson<QuestProgressResponse>(responseText);
                        onSuccess?.Invoke(response);
                    }
                    catch (Exception ex)
                    {
                        ErrorEnvelope parsingError = new ErrorEnvelope
                        {
                            api_version = GameMindConfig.ApiVersion,
                            error = new ErrorDetail { code = "PARSING_ERROR", message = $"Failed to parse response: {ex.Message}" }
                        };
                        onError?.Invoke(parsingError);
                    }
                }
            }
        }

        public IEnumerator GenerateHint(string questId, int hintLevel, Action<HintResponse> onSuccess, Action<ErrorEnvelope> onError)
        {
            string url = $"{GameMindConfig.ApiBaseUrl}/api/v1/hints/generate";
            string jsonPayload = JsonUtility.ToJson(new GenerateHintRequest
            {
                quest_id = questId,
                player_id = defaultPlayerId,
                hint_level = hintLevel
            });

            using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.SetRequestHeader("X-Game-Project-ID", defaultProjectId);
                request.SetRequestHeader("X-Player-ID", defaultPlayerId);
                request.timeout = GameMindConfig.TimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.ProtocolError)
                {
                    HandleError(request, onError);
                }
                else
                {
                    try
                    {
                        string responseText = request.downloadHandler.text;
                        HintResponse response = JsonUtility.FromJson<HintResponse>(responseText);
                        onSuccess?.Invoke(response);
                    }
                    catch (Exception ex)
                    {
                        ErrorEnvelope parsingError = new ErrorEnvelope
                        {
                            api_version = GameMindConfig.ApiVersion,
                            error = new ErrorDetail { code = "PARSING_ERROR", message = $"Failed to parse response: {ex.Message}" }
                        };
                        onError?.Invoke(parsingError);
                    }
                }
            }
        }

        public IEnumerator GetHintStatus(string questId, Action<HintStatusResponse> onSuccess, Action<ErrorEnvelope> onError)
        {
            string url = $"{GameMindConfig.ApiBaseUrl}/api/v1/hints/status?quest_id={UnityWebRequest.EscapeURL(questId)}&player_id={UnityWebRequest.EscapeURL(defaultPlayerId)}";

            using (UnityWebRequest request = UnityWebRequest.Get(url))
            {
                request.SetRequestHeader("X-Game-Project-ID", defaultProjectId);
                request.SetRequestHeader("X-Player-ID", defaultPlayerId);
                request.timeout = GameMindConfig.TimeoutSeconds;

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.ProtocolError)
                {
                    HandleError(request, onError);
                }
                else
                {
                    try
                    {
                        string responseText = request.downloadHandler.text;
                        HintStatusResponse response = JsonUtility.FromJson<HintStatusResponse>(responseText);
                        onSuccess?.Invoke(response);
                    }
                    catch (Exception ex)
                    {
                        ErrorEnvelope parsingError = new ErrorEnvelope
                        {
                            api_version = GameMindConfig.ApiVersion,
                            error = new ErrorDetail { code = "PARSING_ERROR", message = $"Failed to parse response: {ex.Message}" }
                        };
                        onError?.Invoke(parsingError);
                    }
                }
            }
        }

        private void HandleError(UnityWebRequest request, Action<ErrorEnvelope> onError)
        {
            string responseText = request.downloadHandler?.text;
            if (!string.IsNullOrEmpty(responseText))
            {
                try
                {
                    ErrorEnvelope serverError = JsonUtility.FromJson<ErrorEnvelope>(responseText);
                    if (serverError != null && serverError.error != null)
                    {
                        onError?.Invoke(serverError);
                        return;
                    }
                }
                catch {}
            }

            ErrorEnvelope error = new ErrorEnvelope
            {
                api_version = GameMindConfig.ApiVersion,
                error = new ErrorDetail
                {
                    code = "HTTP_ERROR",
                    message = ExtractErrorMessage(responseText, request)
                }
            };
            onError?.Invoke(error);
        }

        private string ExtractErrorMessage(string responseText, UnityWebRequest request)
        {
            if (!string.IsNullOrEmpty(responseText))
            {
                const string detailPrefix = "\"detail\":\"";
                int detailStart = responseText.IndexOf(detailPrefix, StringComparison.Ordinal);
                if (detailStart >= 0)
                {
                    detailStart += detailPrefix.Length;
                    int detailEnd = responseText.IndexOf("\"", detailStart, StringComparison.Ordinal);
                    if (detailEnd > detailStart)
                    {
                        return responseText.Substring(detailStart, detailEnd - detailStart)
                            .Replace("\\\"", "\"")
                            .Replace("\\n", "\n");
                    }
                }

                return responseText;
            }

            return $"HTTP Request failed with result {request.result}. Error: {request.error}";
        }
    }
}
