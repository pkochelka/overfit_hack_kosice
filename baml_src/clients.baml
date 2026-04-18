client<llm> OpenRouterDebtExtractor {
  provider openai-generic
  options {
    base_url "https://openrouter.ai/api/v1"
    api_key env.OPENROUTER_API_KEY
    model "google/gemini-3-flash-preview"
    temperature 0.0
  }
}
