import os
from langchain.document_loaders import PyPDFLoader

BASE_PATH = "storage/policies"

def load_documents():
    documents = []

    for category in ["admin", "hr", "general"]:
        folder = os.path.join(BASE_PATH, category)

        for file in os.listdir(folder):
            if file.endswith(".pdf"):
                path = os.path.join(folder, file)

                loader = PyPDFLoader(path)
                docs = loader.load()

                # 🔥 ADD METADATA
                for d in docs:
                    d.metadata["category"] = category
                    d.metadata["source"] = file

                documents.extend(docs)

    return documents