from langchain.vectorstores import Milvus
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_milvus.retrievers import MilvusCollectionHybridSearchRetriever
from langchain_milvus.utils.sparse import BM25SparseEmbedding
from pymilvus import Collection, connections, CollectionSchema, FieldSchema, DataType, RRFRanker
import pandas as pd



class MilvusHybridSearchHandler:
    """
    Класс для создания, загрузки и использования гибридного поиска в Milvus на LangChain.
    Проверяет, существует ли коллекция, и если нет, то создает её и добавляет данные.
    """
    def __init__(self, collection_name, texts, rag_df, dense_embedding_func, connection_uri="milvus.db"):
        """
        Инициализирует MilvusHybridSearchHandler.

        Параметры:
        - collection_name: Название коллекции Milvus.
        - texts: Список текстов для построения эмбеддингов.
        - rag_df: DataFrame с данными, которые нужно вставить.
        - connection_uri: URI для подключения к Milvus.
        """
        self.collection_name = collection_name
        self.connection_uri = connection_uri
        self._connect()

        self.dense_embedding_func = dense_embedding_func
        self.sparse_embedding_func = BM25SparseEmbedding(corpus=texts, language='ru')
        self.dense_dim = 1024
        self.rag_df = rag_df

    def _connect(self):
        """Подключение к базе данных Milvus."""
        connections.connect(uri=self.connection_uri)

    def _initialize_collection(self) -> Collection:
        """
        Создает новую коллекцию в Milvus с заданной схемой.

        Возвращает:
        - Collection: новая коллекция.
        """
        # определение полей схемы коллекции
        fields = [
            FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, auto_id=True, max_length=100),
            FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=self.dense_dim),
            FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
            FieldSchema(name="main_text", dtype=DataType.VARCHAR, max_length=35000),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="subtitle", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="images", dtype=DataType.VARCHAR, max_length=1000),
        ]
        schema = CollectionSchema(fields=fields)
        collection = Collection(self.collection_name, schema=schema, consistency_level="Eventually")

        collection.create_index("dense_vector", {"index_type": "AUTOINDEX", "metric_type": "IP"})
        collection.create_index("sparse_vector", {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "IP"})
        return collection

    def load_or_create_collection(self) -> Collection:
        """
        Загружает коллекцию, если она существует, или создает новую.

        Возвращает:
        - Collection: загруженная или созданная коллекция.
        """
        try:
            collection = Collection(self.collection_name)
            collection.load()
            print(f"Collection '{self.collection_name}' loaded.")
        except Exception as e:
            print('Exception:', e)
            print(f"Collection '{self.collection_name}' does not exist. Creating a new one.")
            collection = self._initialize_collection()
            collection.load()
        return collection

    def insert_documents(self, collection, rag_df):
        """
        Вставляет документы в коллекцию Milvus.

        Параметры:
        - collection: Milvus коллекция для вставки данных.
        - rag_df: DataFrame с данными для вставки.
        """
        # создание списка документов для вставки в коллекцию
        entities = [
            {
                "dense_vector": self.dense_embedding_func.embed_documents([row["main_text"]])[0],
                "sparse_vector": self.sparse_embedding_func.embed_documents([row["main_text"]])[0],
                "main_text": row["main_text"],
                "title": row.get("title", '') or '',
                "subtitle": row.get("subtitle", '') or '',
                "images": row.get("images", '') or ''
            }
            for _, row in rag_df.iterrows()
        ]
        collection.insert(entities)
        collection.flush()

    def get_retriever(self, top_k: int) -> MilvusCollectionHybridSearchRetriever:
        """
        Загружает или создает коллекцию и возвращает ретривер для гибридного поиска.

        Возвращает:
        - MilvusCollectionHybridSearchRetriever: настроенный ретривер для гибридного поиска.
        """
        collection = self.load_or_create_collection()
        if collection.num_entities == 0:
            self.insert_documents(collection, self.rag_df)

        sparse_search_params = {"metric_type": "IP"}
        dense_search_params = {"metric_type": "IP", "params": {}}

        return MilvusCollectionHybridSearchRetriever(
            collection=collection,
            rerank=RRFRanker(),
            anns_fields=["dense_vector", "sparse_vector"],
            field_embeddings=[self.dense_embedding_func, self.sparse_embedding_func],
            field_search_params=[dense_search_params, sparse_search_params],
            top_k=top_k,
            text_field="main_text"
        )