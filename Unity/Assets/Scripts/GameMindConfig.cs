using UnityEngine;

namespace GameMind
{
    public static class GameMindConfig
    {
        public static readonly string ApiBaseUrl = "http://localhost:8000";
        public static readonly int TimeoutSeconds = 10;
        // Matches BlueprintRuntimeBundleResponse. Keep this explicit so a client
        // notices a contract change instead of silently treating it as runtime data.
        public static readonly string ApiVersion = "1.1";
    }
}
