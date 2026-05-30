import json
import time

import requests

from .base import BaseAgent
from ..config import settings

RAILWAY_GQL = "https://backboard.railway.app/graphql/v2"
JACOBS_REPO = "jimmyardis/jane-jacobs-bot"  # all personas share this repo; PERSONA_ID env var routes them


def _gql(token: str, query: str, variables: dict = None) -> dict:
    resp = requests.post(
        RAILWAY_GQL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Railway GQL error: {data['errors']}")
    return data.get("data", {})


class RailwayDeployerAgent(BaseAgent):
    name = "railway_deployer"
    description = "Creates Railway service for persona, sets env vars, triggers deploy via Railway GraphQL API"
    dependencies = ["page_generator"]

    def run(self, persona_id: str, context: dict) -> dict:
        if not settings.railway_token:
            raise RuntimeError("RAILWAY_TOKEN not set")
        if not settings.railway_project_id:
            raise RuntimeError("RAILWAY_PROJECT_ID not set")
        if not settings.railway_environment_id:
            raise RuntimeError("RAILWAY_ENVIRONMENT_ID not set")

        # Get persona display name from context
        id_result = context.get("persona_identifier", {})
        meta = id_result.get("metadata", {})
        display_name = meta.get("name", persona_id.replace("-", " ").title())

        service_id = self._create_or_get_service(display_name)
        self._connect_repo(service_id)
        railway_url = self._get_or_create_domain(service_id)
        self._set_env_vars(service_id, persona_id)
        deploy_id = self._trigger_deploy(service_id)

        return {
            "status": "ok",
            "service_id": service_id,
            "railway_url": railway_url,
            "deploy_id": deploy_id,
        }

    def _create_or_get_service(self, display_name: str) -> str:
        q = """
        mutation ServiceCreate($input: ServiceCreateInput!) {
          serviceCreate(input: $input) { id name }
        }"""
        try:
            data = _gql(settings.railway_token, q, {
                "input": {"projectId": settings.railway_project_id, "name": display_name}
            })
            return data["serviceCreate"]["id"]
        except RuntimeError as exc:
            if "already exists" not in str(exc).lower():
                raise
            # Look up existing service by name
            return self._find_service_by_name(display_name)

    def _find_service_by_name(self, name: str) -> str:
        q = """
        query Project($id: String!) {
          project(id: $id) {
            services { edges { node { id name } } }
          }
        }"""
        data = _gql(settings.railway_token, q, {"id": settings.railway_project_id})
        for edge in data.get("project", {}).get("services", {}).get("edges", []):
            if edge["node"]["name"] == name:
                return edge["node"]["id"]
        raise RuntimeError(f"Service '{name}' not found in project")

    def _connect_repo(self, service_id: str):
        q = """
        mutation ServiceConnect($id: String!, $input: ServiceConnectInput!) {
          serviceConnect(id: $id, input: $input) { id }
        }"""
        try:
            _gql(settings.railway_token, q, {
                "id": service_id,
                "input": {"repo": settings.railway_source_repo, "branch": "main"},
            })
        except Exception as exc:
            self.logger.warning(f"serviceConnect warning (may already be connected): {exc}")

    def _get_or_create_domain(self, service_id: str) -> str:
        create_q = """
        mutation ServiceDomainCreate($input: ServiceDomainCreateInput!) {
          serviceDomainCreate(input: $input) { domain }
        }"""
        try:
            data = _gql(settings.railway_token, create_q, {
                "input": {
                    "environmentId": settings.railway_environment_id,
                    "serviceId": service_id,
                }
            })
            domain = data.get("serviceDomainCreate", {}).get("domain", "")
            if domain:
                return f"https://{domain}"
        except Exception:
            pass

        # Query existing domain
        q = """
        query Service($id: String!) {
          service(id: $id) {
            serviceInstances {
              edges { node { domains { serviceDomains { domain } } } }
            }
          }
        }"""
        try:
            data = _gql(settings.railway_token, q, {"id": service_id})
            for edge in data.get("service", {}).get("serviceInstances", {}).get("edges", []):
                domains = edge.get("node", {}).get("domains", {}).get("serviceDomains", [])
                if domains:
                    return f"https://{domains[0]['domain']}"
        except Exception:
            pass

        return ""

    def _set_env_vars(self, service_id: str, persona_id: str):
        q = """
        mutation VariablesUpsert($input: VariableCollectionUpsertInput!) {
          variableCollectionUpsert(input: $input)
        }"""
        variables = {
            "PERSONA_ID": persona_id,
            "ANTHROPIC_API_KEY": settings.anthropic_api_key,
            "PINECONE_API_KEY": settings.pinecone_api_key,
            "PINECONE_HOST": settings.pinecone_host,
            "VOYAGE_API_KEY": settings.voyage_api_key,
            "ELEVENLABS_API_KEY": settings.elevenlabs_api_key,
        }
        _gql(settings.railway_token, q, {
            "input": {
                "projectId": settings.railway_project_id,
                "environmentId": settings.railway_environment_id,
                "serviceId": service_id,
                "variables": variables,
            }
        })

    def _trigger_deploy(self, service_id: str) -> str:
        q = """
        mutation Deploy($serviceId: String!, $environmentId: String!) {
          serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
        }"""
        try:
            data = _gql(settings.railway_token, q, {
                "serviceId": service_id,
                "environmentId": settings.railway_environment_id,
            })
            return data.get("serviceInstanceDeployV2", "")
        except Exception as exc:
            self.logger.warning(f"Deploy trigger warning: {exc}")
            return ""
