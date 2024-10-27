import pandas as pd
import os
import docx
import json
from pprint import pprint
from tqdm import tqdm
import torch, gc

from langchain.document_loaders import DataFrameLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS

from extraction.docx_module import DocxHandler
from retriever.milvus_hybrid import MilvusHybridSearchHandler
from rag.llm_module_radmir import LLMManager


class QASystem:
    """
    Система вопросов и ответов (QASystem) для обработки запросов пользователей на основе документов, 
    используя модели эмбеддингов и методы поиска.
    """
    
    def __init__(self, docx_path, csv_path, collection_name, embedding_model="deepvk/USER-bge-m3",
                 connection_uri='milvus.db', num_docs=7, device='cuda'):
        """
        Инициализирует QASystem с документами и моделями эмбеддингов, 
        а также настраивает ретриверы для поиска.

        Параметры:
            docx_path (str): Путь к файлу .docx.
            csv_path (str): Путь к CSV файлу с данными.
            collection_name (str): Имя коллекции в Milvus.
            embedding_model (str, optional): Модель для эмбеддингов. По умолчанию "deepvk/USER-bge-m3".
            connection_uri (str, optional): URI подключения к Milvus. По умолчанию 'milvus.db'.
            num_docs (int, optional): Количество документов для поиска. По умолчанию 7.
            device (str, optional): Устройство для вычислений. По умолчанию 'cuda'.
        """
        self.docx_handler = DocxHandler()
        self.rag_df, self.texts = self.docx_handler.process_file(docx_path, 'data/extracted_images')
        self.rag_df = pd.read_csv(csv_path)[['main_text', 'title', 'subtitle', 'images']].fillna('')

        # Инициализация модели эмбеддингов
        self.hf_embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model, 
            model_kwargs={'device': device}, 
            encode_kwargs={'normalize_embeddings': True}
        )

        # Инициализация обработчика Milvus для гибридного поиска
        self.milvus_handler = MilvusHybridSearchHandler(
            collection_name=collection_name, 
            texts=self.texts, 
            rag_df=self.rag_df,
            connection_uri=connection_uri, 
            dense_embedding_func=self.hf_embeddings
        )

        self.num_docs = num_docs
        self.milvus_retriever = self.milvus_handler.get_retriever(top_k=num_docs) 
        self.faiss_retriever = self._init_faiss_retriever()  
        self.llm = LLMManager() 

    def _init_faiss_retriever(self):
        """
        Инициализирует FAISS ретривер для поиска по тексту с использованием модели эмбеддингов.

        Возвращает:
            faiss_retriever (FAISS): Ретривер для поиска с использованием FAISS.
        """
        loader = DataFrameLoader(self.rag_df, page_content_column='main_text')
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
        faiss_texts = text_splitter.split_documents(documents)
        faiss_retriever = FAISS.from_documents(faiss_texts, self.hf_embeddings).as_retriever(
            search_kwargs={"k": self.num_docs}
        )
        return faiss_retriever

    def answer_question(self, question, use_hyde=True, history=''):
        """
        Обрабатывает вопрос пользователя, выполняя поиск по базе и генерируя ответ с помощью LLM.

        Параметры:
            question (str): Вопрос пользователя.
            use_hyde (bool, optional): Если True, использует hyde для генерации гипотетического документа. По умолчанию True.
            history (str, optional): История предыдущих вопросов. По умолчанию ''.

        Возвращает:
            answer (str): Сгенерированный ответ на вопрос.
        """
        query = self.llm.generate_hypothetical_document(question) if use_hyde else question
        print('Query:', query)
        
        if self.milvus_handler.sparse_embedding_func.embed_query(query) != {}:
            documents = self.milvus_retriever.invoke(query)
        else:
            documents = self.faiss_retriever.invoke(query)
        
        answer = self.llm.llm_question_answer(question, documents, history)
        return answer



if __name__ == "__main__":
    # очистка кэша
    gc.collect()
    torch.cuda.empty_cache()
    
    docx_path = 'data/train/documentation.docx'       # путь к .docx файлу для обработки
    csv_path = 'data/train/rag_df_processed.csv'      # путь к предварительно обработанному .csv файлу
    collection_name = 'sila_collection_test3'         # название коллекции Milvus для dense search
    embedding_model = "deepvk/USER-bge-m3"            # модель векторизации
    connection_uri = 'milvus.db'                      # URI для подключения к базе данных Milvus
    num_docs = 7                                      # количество документов для извлечения по запросу
    device = 'cuda'                                   # устройство для создания векторных представлений (например, 'cuda' или 'cpu')
    
    # определение системного класса
    qa_system = QASystem(
        docx_path=docx_path,
        csv_path=csv_path,
        collection_name=collection_name,
        embedding_model=embedding_model,
        connection_uri=connection_uri,
        num_docs=num_docs,
        device=device
    )

    question = "Как редактировать данные в УЗ?"
    answer = qa_system.answer_question(question, use_hyde=True)
    print(f"\n\n\nОтвет на вопрос {question}: {answer[0]}")
