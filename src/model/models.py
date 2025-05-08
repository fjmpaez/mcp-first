from openai import OpenAI
from abc import ABC, abstractmethod

class ModelClient(ABC):
    """Model Client."""
    
    @abstractmethod
    def chat_completion(self, messages: list[dict], tools: list[dict] = None):
        """It sends a chat completion request to the model."""
        pass

class OpenAIClient(ModelClient):
    """OpenAI Model Client."""
    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
        self.client = OpenAI()

    def chat_completion(self, messages:list, tools: list = None):
        
        args = {
            "model": self.model_name,
            "messages": messages,
        }

        if tools:
            args["tools"] = tools
            args["tool_choice"] = "auto"


        return self.client.chat.completions.create(**args)