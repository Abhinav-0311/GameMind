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
            
            // Build simple JSON manually to avoid depending on third-party JSON libraries in clean setups
            string jsonPayload = $"{{\"npc_slug\":\"{npcSlug}\",\"player_message\":\"{playerMessage}\"";
            if (!string.IsNullOrEmpty(conversationId))
            {
                jsonPayload += $",\"conversation_id\":\"{conversationId}\"";
            }
            jsonPayload += "}";

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
            string jsonPayload = $"{{\"npc_slug\":\"{npcSlug}\",\"player_level\":{playerLevel}}}";

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

        private void HandleError(UnityWebRequest request, Action<ErrorEnvelope> onError)
        {
            string responseText = request.downloadHandler?.text;
            if (!string.IsNullOrEmpty(responseText))
            {
                try
                {
                    ErrorEnvelope serverError = JsonUtility.FromJson<ErrorEnvelope>(responseText);
                    onError?.Invoke(serverError);
                    return;
                }
                catch {}
            }

            // Fallback generic web exception envelope
            ErrorEnvelope error = new ErrorEnvelope
            {
                api_version = GameMindConfig.ApiVersion,
                error = new ErrorDetail
                {
                    code = "HTTP_ERROR",
                    message = $"HTTP Request failed with result {request.result}. Error: {request.error}"
                }
            };
            onError?.Invoke(error);
        }
    }
}
