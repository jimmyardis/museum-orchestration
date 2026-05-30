from typing import Type
from .base import BaseAgent
from .persona_identifier import PersonaIdentifierAgent
from .corpus_fetcher import CorpusFetcherAgent
from .corpus_cleaner import CorpusCleanerAgent
from .pinecone_uploader import PineconeUploaderAgent
from .page_generator import PageGeneratorAgent
from .railway_deployer import RailwayDeployerAgent
from .tts_auditioner import TTSAuditionerAgent

PIPELINE_ORDER = [
    "persona_identifier",
    "corpus_fetcher",
    "corpus_cleaner",
    "pinecone_uploader",
    "page_generator",
    "railway_deployer",
]

OPTIONAL_AGENTS = ["tts_auditioner"]

AGENT_REGISTRY: dict[str, Type[BaseAgent]] = {
    "persona_identifier": PersonaIdentifierAgent,
    "corpus_fetcher": CorpusFetcherAgent,
    "corpus_cleaner": CorpusCleanerAgent,
    "pinecone_uploader": PineconeUploaderAgent,
    "page_generator": PageGeneratorAgent,
    "railway_deployer": RailwayDeployerAgent,
    "tts_auditioner": TTSAuditionerAgent,
}


def get_agent(name: str) -> BaseAgent:
    if name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {name}")
    return AGENT_REGISTRY[name]()


def list_agents() -> list[dict]:
    return [
        {
            "name": cls.name,
            "description": cls.description,
            "dependencies": cls.dependencies,
            "optional": name in OPTIONAL_AGENTS,
        }
        for name, cls in AGENT_REGISTRY.items()
    ]
