from vllm import LLM
from vllm.sampling_params import SamplingParams
from langchain.prompts import PromptTemplate
import json
import csv
import os
import rag.prompts as prompts


class LLMManager:
    """
    Класс для управления взаимодействием с LLM (Large Language Model).
    Содержит методы для генерации ответов, определения типа вопроса, создания гипотетических документов и сохранения ответов.
    
    Атрибуты:
        llm (LLM): Экземпляр модели LLM для генерации текстов.
        system_prompt_template (PromptTemplate): Шаблон для основного системного запроса.
        question_check_template (PromptTemplate): Шаблон для проверки релевантности вопроса.
    """
    
    def __init__(self):
        """
        Инициализирует LLMManager с моделью LLM и шаблонами для системных промптов.
        """
        self.llm = LLM(model="qilowoq/Vikhr-Nemo-12B-Instruct-R-21-09-24-4Bit-GPTQ", max_model_len=8000, dtype='float16')
        self.system_prompt_template = PromptTemplate(
            input_variables=["question", "documents"],
            template=('{system_prompt}\n\nDocuments: {documents}\n\nUsers question: {question}')
        )
        self.question_check_template = PromptTemplate(
            input_variables=["question"],
            template=('{system_prompt}\n\nUsers question: {question}')
        )
        
    def llm_question_answer(self, question, documents, history='') -> str:
        """
        Генерирует ответ на основе заданного вопроса и списка документов.
        
        Параметры:
            question (str): Вопрос пользователя.
            documents (list): Список документов, которые могут быть использованы для ответа.
            history (str, optional): История предыдущих вопросов и ответов. По умолчанию ''.

        Возвращает:
            str: Сгенерированный ответ на вопрос.
        """
        sampling_params = SamplingParams(max_tokens=2048, temperature=0.01)
        
        # 1 ЭТАП: Определение релевантных частей документа для ответа
        FIRST_SYSTEM_PROMPT = prompts.FIRST_SYSTEM_PROMPT
        cleaned_docs = [{'id': i, 'main_text': doc.page_content, 'images': doc.metadata['images']} for i, doc in enumerate(documents)]
        titles = [{'id': i, 'title': doc.metadata['title'] + ' \\ ' + doc.metadata['subtitle']} for i, doc in enumerate(documents)]

        generated_answer = self._generate_answer(cleaned_docs, FIRST_SYSTEM_PROMPT, question, sampling_params)
        relevant_indexes = json.loads(generated_answer[0].outputs[0].text)['relevant_doc_ids']
        print('relevant indexes:', relevant_indexes)

        # 1.1 ЭТАП: Проверка релевантности вопроса
        if not relevant_indexes:
            question_type = self.define_question_type(question)
            print('question_type', question_type)
            if question_type == 'Да':
                return ('К сожалению, на данный момент я не могу ответить на ваш вопрос:(\n'
                        'Вы можете обратиться в техническую поддержку нашего сервиса:\n'
                        '**+7-(495)-258-06-36**\n**info@lense.ru**\n**lense.ru**\n\n'
                        'Также вы можете сами ознакомиться с документацией.'), [], []
            else:
                return 'К сожалению, я не могу ответить на ваш вопрос. Попробуйте переформулировать его и задать снова', [], []

        # 2 ЭТАП: Генерация ответа на основе релевантных частей документа
        filtered_documents = [doc for doc in cleaned_docs if doc['id'] in relevant_indexes]
        filtered_titles = list(set([doc['title'] for doc in titles if doc['id'] in relevant_indexes]))
        print(filtered_documents)

        SECOND_SYSTEM_PROMPT = prompts.SECOND_SYSTEM_PROMPT
        if history:
            SECOND_SYSTEM_PROMPT += f'\nPrevious user questions were {history}'

        generated_answer = self._generate_answer(filtered_documents, SECOND_SYSTEM_PROMPT, question, sampling_params)[0].outputs[0].text
        print('generated_answer', generated_answer)

        self.save_to_csv(question, generated_answer, filtered_documents)

        # 3 ЭТАП: Выбор изображений, подходящих под контекст
        THIRD_SYSTEM_PROMPT = prompts.THIRD_SYSTEM_PROMPT
        paths_with_titles = sum([sum(eval(doc['images']), []) for doc in filtered_documents], [])
        if paths_with_titles:
            print('paths_with_titles', paths_with_titles)
            photo_documents = [{'id': index, 'title': '', "context": i['description']} for index, i in enumerate(paths_with_titles)]
            llm_photos_ids = self._generate_answer(photo_documents, THIRD_SYSTEM_PROMPT, question + ' | ' + generated_answer, sampling_params)[0].outputs[0].text
            print('llm_photos_ids', llm_photos_ids)
            
            try:
                llm_photos_ids = json.loads(llm_photos_ids)['relevant_doc_ids']
                llm_photos_paths = [paths_with_titles[ind] for ind in llm_photos_ids]
                return generated_answer, llm_photos_paths[:1], filtered_titles
            except:
                return generated_answer, [], filtered_titles
        else:
            return generated_answer, [], filtered_titles

    def define_question_type(self, question):
        """
        Определяет, релевантен ли вопрос для обработки с использованием системы.
        
        Параметры:
            question (str): Вопрос пользователя.

        Возвращает:
            str: Тип вопроса ('Да' или 'Нет').
        """
        summary = prompts.summary + question
        messages = [{"role": "system", "content": summary}]
        sampling_params = SamplingParams(max_tokens=50, temperature=0.01)

        hypo_output = self.llm.chat(messages=messages, sampling_params=sampling_params)
        return hypo_output[0].outputs[0].text

    def generate_hypothetical_document(self, question):
        """
        Генерирует гипотетический документ, соответствующий вопросу пользователя.
        
        Параметры:
            question (str): Вопрос пользователя.

        Возвращает:
            str: Сгенерированный гипотетический документ.
        """
        hypo_prompt = prompts.hypo_prompt + question
        messages = [{"role": "system", "content": hypo_prompt}]
        sampling_params = SamplingParams(max_tokens=300, temperature=0.01)

        hypo_output = self.llm.chat(messages=messages, sampling_params=sampling_params)
        return question + ' | ' + hypo_output[0].outputs[0].text

    def _generate_answer(self, docs, system_prompt, question, sampling_params):
        """
        Формирует системный запрос и отправляет его в LLM для генерации ответа.

        Параметры:
            docs (list): Список документов для обработки.
            system_prompt (str): Системный запрос для LLM.
            question (str): Вопрос пользователя.
            sampling_params (SamplingParams): Параметры для генерации текста.

        Возвращает:
            str: Ответ, сгенерированный LLM.
        """
        filtered_document_content = json.dumps(docs, ensure_ascii=False)
        final_prompt = self.system_prompt_template.format(
            system_prompt=system_prompt,
            documents=filtered_document_content,
            question=question,
        )
        
        messages = [{"role": "system", "content": final_prompt}]
        return self.llm.chat(messages=messages, sampling_params=sampling_params)

    def save_to_csv(self, question, answer, filtered_documents):
        """
        Сохраняет вопрос, ответ и отфильтрованные документы в файл CSV для последующего анализа.

        Параметры:
            question (str): Вопрос пользователя.
            answer (str): Сгенерированный ответ.
            filtered_documents (list): Список релевантных документов.
        """
        csv_file = "answers_log.csv"
        file_exists = os.path.isfile(csv_file)
        document_texts = [doc['main_text'] for doc in filtered_documents]
        
        with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Question", "Answer", "Filtered Documents"])
            writer.writerow([question, answer, '\n\n'.join(document_texts)])
