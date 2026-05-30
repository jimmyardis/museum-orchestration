from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Museum project root — where personas/ directory lives
    museum_root: str = "/home/wner"

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_host: str = "museum-of-minds-vfyxzen.svc.aped-4627-b74a.pinecone.io"
    pinecone_index: str = "museum-of-minds"

    # Voyage AI (for embeddings)
    voyage_api_key: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # ElevenLabs
    elevenlabs_api_key: str = ""

    # GitHub (for page_generator)
    github_token: str = ""
    github_username: str = "jimmyardis"
    museum_repo: str = "jimmyardis/museum-of-minds"

    # Railway (for railway_deployer)
    railway_token: str = ""
    railway_project_id: str = ""        # giving-expression project ID
    railway_environment_id: str = ""    # production environment ID
    railway_source_repo: str = "jimmyardis/jane-jacobs-bot"  # all persona services use this repo

    # Service
    database_path: str = "./orchestrator.db"
    port: int = 8080

    class Config:
        env_file = ".env"


settings = Settings()
