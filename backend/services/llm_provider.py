"""
Shared LLM provider helpers with OpenAI/Azure OpenAI fallback logic.
"""
from __future__ import annotations

import os
from typing import Any, Optional


def _clean_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def using_azure_openai() -> bool:
    """Return True when Azure OpenAI endpoint is configured."""
    return bool(_clean_env("AZURE_OPENAI_ENDPOINT"))


def _azure_api_key() -> str:
    return _clean_env("AZURE_OPENAI_API_KEY") or _clean_env("OPENAI_API_KEY")


def _openai_api_key() -> str:
    return _clean_env("OPENAI_API_KEY")


def has_llm_credentials() -> bool:
    """Return True when credentials are available for configured provider."""
    if using_azure_openai():
        return bool(_azure_api_key())
    return bool(_openai_api_key())


def get_openai_client() -> Optional[Any]:
    """
    Return configured OpenAI-compatible client.
    - Azure mode: AzureOpenAI(api_key, azure_endpoint, api_version)
    - OpenAI mode: OpenAI(api_key)
    """
    try:
        from openai import OpenAI, AzureOpenAI
    except ImportError:
        return None

    if using_azure_openai():
        endpoint = _clean_env("AZURE_OPENAI_ENDPOINT")
        key = _azure_api_key()
        api_version = _clean_env("AZURE_OPENAI_API_VERSION") or "2024-02-01"
        if not endpoint or not key:
            return None
        return AzureOpenAI(api_key=key, azure_endpoint=endpoint, api_version=api_version)

    key = _openai_api_key()
    if not key:
        return None
    return OpenAI(api_key=key)


def resolve_chat_model(default_model: str, *, deployment_env: Optional[str] = None) -> str:
    """
    Resolve model/deployment name for chat completions.
    In Azure mode, deployment names must be used.
    """
    if using_azure_openai():
        if deployment_env:
            dep = _clean_env(deployment_env)
            if dep:
                return dep
        generic_dep = _clean_env("AZURE_OPENAI_CHAT_DEPLOYMENT")
        if generic_dep:
            return generic_dep
    return default_model


def get_langchain_chat_model(
    *,
    default_model: str,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    deployment_env: Optional[str] = None,
    model_kwargs: Optional[dict] = None,
):
    """
    Return a LangChain chat model configured for OpenAI or Azure OpenAI.
    """
    if not has_llm_credentials():
        return None

    if using_azure_openai():
        from langchain_openai import AzureChatOpenAI

        endpoint = _clean_env("AZURE_OPENAI_ENDPOINT")
        key = _azure_api_key()
        api_version = _clean_env("AZURE_OPENAI_API_VERSION") or "2024-02-01"
        deployment = resolve_chat_model(default_model, deployment_env=deployment_env)
        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version=api_version,
            azure_deployment=deployment,
            temperature=temperature,
            max_tokens=max_tokens,
            model_kwargs=model_kwargs or {},
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=default_model,
        api_key=_openai_api_key(),
        temperature=temperature,
        max_tokens=max_tokens,
        model_kwargs=model_kwargs or {},
    )


def get_langchain_embeddings(*, default_model: str = "text-embedding-3-small", deployment_env: Optional[str] = None):
    """Return LangChain embeddings client for OpenAI/Azure OpenAI."""
    if not has_llm_credentials():
        return None

    if using_azure_openai():
        from langchain_openai import AzureOpenAIEmbeddings

        endpoint = _clean_env("AZURE_OPENAI_ENDPOINT")
        key = _azure_api_key()
        api_version = _clean_env("AZURE_OPENAI_API_VERSION") or "2024-02-01"
        deployment = resolve_chat_model(default_model, deployment_env=deployment_env or "AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        return AzureOpenAIEmbeddings(
            azure_endpoint=endpoint,
            api_key=key,
            api_version=api_version,
            azure_deployment=deployment,
        )

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=default_model, api_key=_openai_api_key())
