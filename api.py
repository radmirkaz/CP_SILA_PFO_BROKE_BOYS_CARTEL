from fastapi import FastAPI
from main import QASystem
from pydantic import BaseModel
import torch

class QueryRequest(BaseModel):
    """ 
    Модель данных для запроса с вопросом пользователя и историей предыдущих вопросов.
    
    Атрибуты:
        query (str): Текст вопроса пользователя.
        history (str): История предыдущих вопросов и ответов для контекста.
    """
    query: str
    history: str

app = FastAPI()

# Инициализация системы вопросов и ответов с загрузкой документов и настройкой модели эмбеддингов
qa_system = QASystem(
    docx_path='data/train/documentation.docx',
    csv_path='data/train/rag_df_processed.csv',
    collection_name='sila_collection_test3',
    embedding_model="deepvk/USER-bge-m3",
    connection_uri='milvus.db',
    num_docs=7,
    device='cuda'
)

@app.post("/predict")
async def predict(request: QueryRequest):
    """ 
    Эндпоинт для предсказания ответа на основе вопроса пользователя и истории.
    
    Принимает объект `QueryRequest` с вопросом и историей, обрабатывает запрос через `qa_system`,
    возвращает сгенерированный ответ, список связанных изображений и заголовков.

    Параметры:
        request (QueryRequest): Запрос с текстом вопроса и историей.

    Возвращает:
        dict: JSON-ответ с ключами "answer", "photos" и "titles".
    """
    torch.cuda.empty_cache()  # очистка кэша GPU для освобождения памяти
    question = request.query
    history = request.history
    answer, photos, titles = qa_system.answer_question(question, use_hyde=True, history='')
    return {"answer": answer, 'photos': photos, 'titles': titles}