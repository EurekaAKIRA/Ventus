from lavague.core.token_counter import TokenCounter
from llama_index.llms.openai import OpenAI
from llama_index.multi_modal_llms.openai import OpenAIMultiModal
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.base.llms.types import LLMMetadata
from lavague.core.context import Context
from openai import OpenAI as OpenAIClient
import os
import json
from urllib import request, error

llm_name = os.getenv("DEEPSEEK_LLM_MODEL", "deepseek-chat")
mm_llm_name = os.getenv(
    "HUNYUAN_MM_LLM_MODEL",
    os.getenv("OPENAI_MM_LLM_MODEL", "hunyuan-vision"),
)
embedding_name = os.getenv(
    "ARK_EMBEDDING_MODEL",
    os.getenv("DOUBAO_EMBEDDING_MODEL", "doubao-embedding-vision-251215"),
)


class DeepSeekOpenAICompatibleEmbedding(BaseEmbedding):
    api_key: str
    api_base: str
    model_name: str = embedding_name

    def _embed_text_with_ark_multimodal_api(self, text: str):
        endpoint = self.api_base.rstrip("/") + "/embeddings/multimodal"
        payload = {
            "model": self.model_name,
            "input": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                "ARK multimodal embedding request failed with "
                f"status {exc.code}: {details}"
            ) from exc

        try:
            data = body["data"]
            if isinstance(data, list):
                return data[0]["embedding"]
            return data["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "Unexpected response format from ARK multimodal embeddings API: "
                f"{body}"
            ) from exc

    def _embed_texts(self, texts):
        if self.model_name.startswith("doubao-embedding-vision"):
            return [
                self._embed_text_with_ark_multimodal_api(text) for text in texts
            ]

        client = OpenAIClient(
            api_key=self.api_key,
            base_url=self.api_base,
        )
        response = client.embeddings.create(
            model=self.model_name,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def _get_query_embedding(self, query: str):
        return self._embed_texts([query])[0]

    async def _aget_query_embedding(self, query: str):
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str):
        return self._embed_texts([text])[0]

    def _get_text_embeddings(self, texts):
        return self._embed_texts(texts)


class DeepSeekOpenAICompatibleLLM(OpenAI):
    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=128000,
            num_output=self.max_tokens or -1,
            is_chat_model=True,
            is_function_calling_model=False,
            model_name=self.model,
        )


class DeepSeekOpenAICompatibleMultiModal(OpenAIMultiModal):
    def _get_model_kwargs(self, **kwargs):
        base_kwargs = {"model": self.model, "temperature": self.temperature, **kwargs}
        if self.max_new_tokens is not None:
            base_kwargs["max_tokens"] = self.max_new_tokens
        return {**base_kwargs, **self.additional_kwargs}

# declare the token counter before any LLMs are initialized
token_counter = TokenCounter()

llm_api_key = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY"))
llm_api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")

mm_api_key = os.getenv(
    "HUNYUAN_API_KEY",
    os.getenv("OPENAI_API_KEY", llm_api_key),
)
mm_api_base = os.getenv(
    "HUNYUAN_API_BASE",
    os.getenv("OPENAI_API_BASE", "https://api.hunyuan.cloud.tencent.com/v1"),
)

embedding_api_key = os.getenv(
    "ARK_API_KEY",
    os.getenv("DOUBAO_API_KEY", llm_api_key),
)
embedding_api_base = os.getenv(
    "ARK_API_BASE",
    os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3"),
)

# init models
llm = DeepSeekOpenAICompatibleLLM(
    model=llm_name, api_key=llm_api_key, api_base=llm_api_base
)
mm_llm = DeepSeekOpenAICompatibleMultiModal(
    model=mm_llm_name, api_key=mm_api_key, api_base=mm_api_base
)
embedding = DeepSeekOpenAICompatibleEmbedding(
    model_name=embedding_name,
    api_key=embedding_api_key,
    api_base=embedding_api_base,
)

# init context
context = Context(llm, mm_llm, embedding)
