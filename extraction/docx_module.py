import os
import docx
from docx.opc.constants import RELATIONSHIP_TYPE as RT
import pandas as pd


# Класс для обработки .docx файлов и извлечения текста и изображений с их структурированием
class DocxHandler():
    def extract_text_from_docx(self, docx_path, images_path='extracted_images'):
        """Извлекает текст и изображения из .docx файла и сохраняет их в структуре данных."""
        os.makedirs(images_path, exist_ok=True)
        # Open the document
        doc = docx.Document(docx_path)

        # Define structure to store headings and content
        document_structure = []

        current_section = {}
        current_subsection = {}
        current_subsubsection = {}
        current_level = None
        image_count = 0
        processed_images = {}  # Dictionary to track processed images

        paragraphs = doc.paragraphs
        total_paragraphs = len(paragraphs)
        i = 0  # Paragraph index

        while i < total_paragraphs:
            para = paragraphs[i]
            style = para.style.name

            # Initialize images list at the current level if not already
            if current_level == 3:
                if 'images' not in current_subsubsection:
                    current_subsubsection['images'] = []
            elif current_level == 2:
                if 'images' not in current_subsection:
                    current_subsection['images'] = []
            elif current_level == 1:
                if 'images' not in current_section:
                    current_section['images'] = []

            # Iterate through runs with their indices
            for run_idx, run in enumerate(para.runs):
                # Check if the run contains a drawing (which may include images)
                drawing = run._element.xpath('.//a:blip')
                if drawing:
                    # Extract the relationship ID
                    blip = drawing[0]
                    embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if embed and embed not in processed_images:
                        # Get the relationship object
                        rel = doc.part.rels.get(embed)
                        if rel and rel.reltype == RT.IMAGE:
                            image_count += 1
                            # Preserve original image extension
                            image_extension = os.path.splitext(rel.target_ref)[1]
                            # Handle cases where image_extension might be empty
                            if not image_extension:
                                image_extension = '.png'  # Default to .png if extension is missing
                            image_filename = f"image_{image_count}{image_extension}"
                            image_path = os.path.join(images_path, image_filename)
                            with open(image_path, "wb") as f:
                                f.write(rel.target_part.blob)
                            # Map the relationship ID to the image filename
                            processed_images[embed] = image_filename

                    # Add image reference to the images list
                    if embed in processed_images:
                        image_entry = {
                            'path': os.path.join(images_path, processed_images[embed]),
                            'description': ''
                        }

                        # Attempt to extract the description
                        # Assume the description is in the same paragraph after the image or in the next paragraph
                        description_found = False

                        # Check remaining runs in the current paragraph
                        for subsequent_run in para.runs[run_idx + 1:]:
                            text = subsequent_run.text.strip()
                            if text.startswith('Рисунок'):
                                image_entry['description'] = text
                                description_found = True
                                break

                        if not description_found:
                            # Check the next paragraph
                            if i + 1 < total_paragraphs:
                                next_para = paragraphs[i + 1]
                                next_text = next_para.text.strip()
                                if next_text.startswith('Рисунок'):
                                    image_entry['description'] = next_text
                                    # Skip the next paragraph as it's the description
                                    i += 1
                        # Append the image entry to the appropriate images list
                        if current_level == 3:
                            current_subsubsection['images'].append(image_entry)
                        elif current_level == 2:
                            current_subsection['images'].append(image_entry)
                        elif current_level == 1:
                            current_section['images'].append(image_entry)

            # If the paragraph is a heading
            if style.startswith("Heading"):
                # Determine the heading level
                try:
                    level = int(style.split(" ")[1])
                except (IndexError, ValueError):
                    # If the style name doesn't follow the expected pattern, skip
                    i += 1
                    continue

                # If it's a level 1 heading
                if level == 1:
                    # If there's an existing section, add it to the structure
                    if current_section:
                        document_structure.append(current_section)
                    # Start a new section with 'content' initialized
                    current_section = {'title': para.text, 'subsections': [], 'content': ''}
                    current_level = level
                    current_subsection = {}
                    current_subsubsection = {}
                # If it's a level 2 heading
                elif level == 2:
                    # Start a new subsection
                    current_subsection = {'subtitle': para.text, 'subsubsections': [], 'content': ''}
                    current_section['subsections'].append(current_subsection)
                    current_level = level
                    current_subsubsection = {}
                # If it's a level 3 heading
                elif level == 3:
                    # Start a new sub-subsection
                    current_subsubsection = {'subsubtitle': para.text, 'content': ''}
                    current_subsection['subsubsections'].append(current_subsubsection)
                    current_level = level
            else:
                # If it's not a heading, add text to the current sub-subsection, subsection, or section
                text = para.text.strip()
                if text:
                    if current_level == 3:
                        current_subsubsection['content'] += text + '\n'
                    elif current_level == 2:
                        current_subsection['content'] += text + '\n'
                    elif current_level == 1:
                        current_section['content'] += text + '\n'

            i += 1  # Move to the next paragraph

        # Add the last section if it exists
        if current_section:
            document_structure.append(current_section)

        return document_structure


    def clean_document_structure(self, document_structure):
        """Очищает структуру документа, убирая лишние символы и пустые разделы."""
        
        # Helper function to clean content and remove unwanted newlines
        def clean_content(content):
            return content.replace('\n', ' ').strip()

        # Iterate over each section in the document structure
        cleaned_structure = []
        for section in document_structure:
            # Clean the content of the section, if it exists
            if 'content' in section:
                section['content'] = clean_content(section['content'])

            # Process subsections if they exist
            if 'subsections' in section:
                cleaned_subsections = []
                for subsection in section['subsections']:
                    # Clean the content of the subsection
                    if 'content' in subsection:
                        subsection['content'] = clean_content(subsection['content'])

                    # Process sub-subsections if they exist
                    if 'subsubsections' in subsection:
                        cleaned_subsubsections = []
                        for subsubsection in subsection['subsubsections']:
                            # Clean the content of the sub-subsection
                            if 'content' in subsubsection:
                                subsubsection['content'] = clean_content(subsubsection['content'])

                            # Include only sub-subsections with non-empty content
                            if subsubsection['content'] or subsubsection.get('images'):
                                cleaned_subsubsections.append(subsubsection)

                        # Update the subsection with cleaned sub-subsections
                        subsection['subsubsections'] = cleaned_subsubsections

                    # Include only subsections with non-empty content or sub-subsections
                    if subsection.get('content', []) or subsection.get('subsubsections', []) or subsection.get('images', []):
                        cleaned_subsections.append(subsection)

                # Update the section with cleaned subsections
                section['subsections'] = cleaned_subsections

            # Include only sections with non-empty content or non-empty subsections
            if section.get('content', []) or section.get('subsections', []) or section.get('images', []):
                cleaned_structure.append(section)
        return cleaned_structure


    def structure_chunks(self, cleaned_chunks):
        """Создает структуру данных для обработки на уровне заголовков и подзаголовков."""
        sub_headers = []

        for i, section in enumerate(cleaned_chunks):
            # 1. Add the main content of the section, if it exists
            if 'content' in section and section['content'].strip():
                sub_headers.append({
                    'question_id': i,
                    'sub_question_id': None,
                    'title': section['title'],
                    'main_text': f"Название секции: {section['title']} | Текст секции: {section['content']}",
                    'images': section.get('images', [])
                })

            # 2. Add subsections of the section
            for subi, subsection in enumerate(section.get('subsections', [])):
                # Add the main content of the subsection, if it exists
                if 'content' in subsection and subsection['content'].strip():
                    sub_headers.append({
                        'question_id': i,
                        'sub_question_id': subi,
                        'title': section['title'],
                        'subtitle': subsection['subtitle'],
                        'main_text': f"Название секции: {section['title']} / {subsection['subtitle']} | Текст секции: {subsection['content']}",
                        'images': subsection.get('images', [])
                    })

                # 3. Add sub-subsections of the subsection
                for subsubi, subsubsection in enumerate(subsection.get('subsubsections', [])):
                    # Add the content of the sub-subsection, if it exists
                    if 'content' in subsubsection and subsubsection['content'].strip():
                        sub_headers.append({
                            'question_id': i,
                            'sub_question_id': f"{subi}.{subsubi}",
                            'title': section['title'],
                            'subtitle': subsection['subtitle'],
                            'subsubtitle': subsubsection['subsubtitle'],
                            'main_text': f"Название секции: {section['title']} / {subsection['subtitle']} / {subsubsection['subsubtitle']} |  Текст секции: {subsubsection['content']}",
                            'images': subsubsection.get('images', [])
                        })
        return sub_headers


    def process_file(self, docx_path, images_path='data/extracted_images'):
        """Основной метод для обработки файла: извлекает текст и изображения, очищает и структурирует данные."""
        document_structure1 = self.extract_text_from_docx(docx_path, images_path)
        cleaned = self.clean_document_structure(document_structure1)
        total_headers = self.structure_chunks(cleaned)
        final_df = pd.DataFrame(total_headers)[['question_id', 'sub_question_id', 'main_text', 'images', 'title', 'subtitle', 'subsubtitle']].fillna('')
        texts = final_df["main_text"].tolist()
        return final_df, texts