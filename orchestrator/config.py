from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pinecone_api_key: str = ""
    pinecone_host: str = "museum-of-minds-vfyxzen.svc.aped-4627-b74a.pinecone.io"
    pinecone_index: str = "museum-of-minds"
    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    railway_token: str = ""
    database_path: str = "./orchestrator.db"
    port: int = 8080

    class Config:
        env_file = ".env"


settings = Settings()
