import streamlit as st
import os
import re
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from chromadb.config import Settings
from dotenv import load_dotenv

load_dotenv()

st.title("SamvidhanAI - Your Legal Assistant")

PDF_PATH = "constitution.pdf"
CHROMA_DB_PATH = "chroma_db"

if "chat_history" not in st.session_state:  
    st.session_state.chat_history = []
if "memory_context" not in st.session_state:
    st.session_state.memory_context = ""

if not os.path.exists(CHROMA_DB_PATH):
    with st.spinner("🔹 Loading legal knowledge base... Please wait."):
        loader = PyPDFLoader(PDF_PATH)
        data = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
        docs = text_splitter.split_documents(data)
        vectorstore = Chroma.from_documents(
            documents=docs, 
            embedding=GoogleGenerativeAIEmbeddings(model="models/embedding-001"),
            persist_directory=CHROMA_DB_PATH,
            client_settings=Settings(anonymized_telemetry=False)
        )
    st.success("✅ Legal knowledge base loaded successfully!")
else:
    vectorstore = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=GoogleGenerativeAIEmbeddings(model="models/embedding-001"))

retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 10})

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.4, max_tokens=1000, top_p=0.95, top_k=40)

system_prompt = (
    "You are an AI legal assistant that provides **structured, well-formatted, and factual** legal guidance. "
    "Ensure responses are clear and professional.\n\n"

    "## **Response Formatting Rules:**\n"
    "✔ **Use headings and subheadings** for clarity.\n"
    "✔ **Use bullet points or numbering** where applicable.\n"
    "✔ **Avoid referencing unrelated legal articles** unless mentioned by the user.\n"
    "✔ **Summarize key takeaways** at the end.\n\n"

    "**Chat History Context:** {context}\n"
    "User Query: {input}"
)

def format_response(text):
    text = text.replace("- ", "✔ ")

    text = re.sub(r'(\d+)\. ', r'**\1.** ', text)

    return f"{text}\n\n---\n✅ *Need more details? Feel free to ask!*"

for role, message in st.session_state.chat_history:
    with st.chat_message("user" if role == "User" else "assistant"):
        st.markdown(message)

query = st.chat_input("Ask your legal question...")

if query:
    with st.status("🔍 Analyzing legal context...", expanded=True):
        full_context = st.session_state.memory_context + "\n".join([msg for role, msg in st.session_state.chat_history])

        question_answer_chain = create_stuff_documents_chain(
            llm, ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{input}")])
        )
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        response = rag_chain.invoke({"context": full_context, "input": query})

    if "answer" in response:
        formatted_response = format_response(response["answer"])

        st.session_state.chat_history.append(("User", query))
        st.session_state.chat_history.append(("AI", formatted_response))
        st.session_state.memory_context += query + "\n" + response["answer"] + "\n"

        with st.chat_message("user"):
            st.markdown(query)
        with st.chat_message("assistant"):
            st.markdown(formatted_response)
    else:
        st.error("⚠️ No response generated. Please try again.")
