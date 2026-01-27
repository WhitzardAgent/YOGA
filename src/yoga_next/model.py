from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Optional, Dict, Any
import logging


class Model:
    """
    A class that wraps the OpenAI client with tenacity for robustness,
    allowing configuration of api_base, api_key, and model_name.
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 api_base: Optional[str] = None, 
                 model_name: str = "gpt-3.5-turbo",
                 max_retries: int = 3):
        """
        Initialize the Model with OpenAI client and tenacity retry configuration.
        
        Args:
            api_key: OpenAI API key. If not provided, will use environment variable OPENAI_API_KEY
            api_base: OpenAI API base URL. If not provided, will use default OpenAI API endpoint
            model_name: The model to use for completions (default: gpt-3.5-turbo)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.client = OpenAI(api_key=api_key, base_url=api_base)
        self.model_name = model_name
        self.max_retries = max_retries
        
        # Configure retry decorator
        self._retry_decorator = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type((Exception,))  # Retry on all exceptions by default
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def chat_completion(self, 
                       messages: list, 
                       temperature: float = 0.7, 
                       max_tokens: Optional[int] = None,
                       **kwargs) -> Any:
        """
        Create a chat completion using the OpenAI client with retry logic.
        
        Args:
            messages: List of message dictionaries in the format {"role": "...", "content": "..."}
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum number of tokens to generate (optional)
            **kwargs: Additional arguments to pass to the OpenAI client
            
        Returns:
            Response from OpenAI API
        """
        params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
            
        # Add any additional parameters
        params.update(kwargs)
        
        try:
            response = self.client.chat.completions.create(**params)
            res =  response.choices[0].message.content
            if('<minimax:tool_call>' in res):
                res = res.replace('<minimax:tool_call>', '')
            if('</minimax:tool_call>' in res):
                res = res.replace('</minimax:tool_call>', '')
            return res

        except Exception as e:
            logging.error(f"Error in chat_completion: {str(e)}")
            raise
    
    def completion_with_retry(self, 
                              messages: list, 
                              temperature: float = 0.7, 
                              max_tokens: Optional[int] = None,
                              **kwargs) -> Any:
        """
        Wrapper method to call chat_completion with the retry decorator applied dynamically.
        This allows using the instance's retry configuration.
        """
        return self._retry_decorator(
            lambda: self.chat_completion(
                messages=messages, 
                temperature=temperature, 
                max_tokens=max_tokens, 
                **kwargs
            )
        )()
    
    def simple_inference(self, 
                         prompt: str, 
                         system_prompt: Optional[str] = None,
                         temperature: float = 0.7, 
                         max_tokens: Optional[int] = None,
                         **kwargs) -> str:
        """
        Perform a simple inference with the model.
        
        Args:
            prompt: The user prompt to send to the model
            system_prompt: Optional system prompt to set the behavior (default: None)
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum number of tokens to generate (optional)
            **kwargs: Additional arguments to pass to the OpenAI client
            
        Returns:
            Generated text response from the model
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        messages.append({"role": "user", "content": prompt})
        
        response = self.completion_with_retry(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response.choices[0].message.content