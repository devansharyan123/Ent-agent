import os


class Settings:
    """Application configuration"""

    # Database
    database_url: str = os.getenv("DATABASE_URL", "")

    # LLM Configuration
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "mixtral-8x7b-32768")
    agent_temperature: float = float(os.getenv("AGENT_TEMPERATURE", "0.7"))

    # Vector Store Configuration
    vector_store_dimension: int = int(os.getenv("VECTOR_STORE_DIMENSION", "1536"))

    # Agent Configuration
    agent_timeout: int = 30  # seconds
    max_conversation_history: int = 10  # messages to keep in context
    cache_ttl: int = 3600  # seconds


settings = Settings()
