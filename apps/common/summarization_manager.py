from .utils import tokenize, get_llm
from langchain.text_splitter import TokenTextSplitter
from langchain.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import tiktoken
from django.conf import settings
import logging
from langchain.callbacks.manager import CallbackManager
from .utils import tokenize, get_llm,  TokenCounterCallback
from django.utils import timezone

class SummarizationManager:
    def __init__(self, model_name:str, task_instance = None):
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        #self.llm=get_llm(model_name, temperature=0.0)
        self.model_name = model_name
        self.task_instance = task_instance
        self.llm, self.token_counter_callback = get_llm(model_name, temperature=0.0)    
        
    def summarize_content(self, content: str) -> str:
        
        content_tokens = tokenize(content, self.tokenizer)
        #logging.info(f'summarize_content {content_tokens} tokens: {content[:100]}')

        if content_tokens < 20:
            return f"##### TITLE: {content}",0,0
        todays_date=timezone.now().strftime("%Y-%m-%d")
        summarize_prompt = ChatPromptTemplate.from_messages([
            ("human", 
            """
Rewrite this text in the style of a textbook chapter for 9th graders.
                Text:{content}                   
            """),
        ])

        summarize_chain = summarize_prompt| self.llm | StrOutputParser()

        self.task_instance.update_state(
            state='summarizing content',
            meta={'current_chunk': 0, 'total_chunks': 1}           
        )

        summary = summarize_chain.invoke({'content':content, 'date':todays_date})

        input_tokens = self.token_counter_callback.input_tokens
        output_tokens = self.token_counter_callback.output_tokens
        #logging.info(f"Summarization Input tokens: {input_tokens}, output tokens: {output_tokens}")
        return summary, input_tokens, output_tokens


