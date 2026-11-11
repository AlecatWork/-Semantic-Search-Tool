import streamlit as st
import chromadb
import os

st.set_page_config(page_title="Semantic Search", page_icon="🔍", layout="wide")


GREEN_MAX = 1.0
YELLOW_MAX = 1.4

# --- ChromaDB Setup ---
@st.cache_resource  # Cache the client so it persists across re-runs
def get_collection():
    client = chromadb.PersistentClient(path="./search_db")
    return client.get_or_create_collection(name="course_docs")

collection = get_collection()



# --- Document Loading & Chunking ---
def load_and_chunk(directory):
    """Load .txt/.md files and split into paragraph chunks."""
    chunks = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(('.txt', '.md')):
            continue
        with open(os.path.join(directory, filename), "r", encoding='utf-8') as f:
            content = f.read()

        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        for i, para in enumerate(paragraphs):
            chunks.append({
                "text": para,
                "source": filename,
                "chunk_id": f"{filename}_{i}",
                "chunk_index": i,
            })
    return chunks

def get_sources():
    """Unique source filenames currently stored in the collection"""
    data = collection.get(include=["metadatas"])
    return sorted({m["source"] for m in data["metadatas"]})


def relevance_badge(distance):
    if distance < GREEN_MAX:
        return "🟢 High"
    if distance < YELLOW_MAX:
        return "🟡 Medium"
    return "🔴 Low"


def set_query(text):
    st.session_state["query"] = text





# --- Sidebar: Ingestion Controls ---
with st.sidebar:
    st.title("📁 Document Manager")

    if st.button("🔄 Re-index Documents"):
        chunks = load_and_chunk("docs")
        if chunks:
            collection.upsert(
                documents=[c["text"] for c in chunks],
                metadatas=[{"source": c["source"], "chunk_index": str(c["chunk_index"])} for c in chunks],
                ids=[c["chunk_id"] for c in chunks],
            )
            st.success(f"Indexed {len(chunks)} chunks from {len(set(c['source'] for c in chunks))} files")
        else:
            st.warning("No .txt or .md files found in docs/ folder")


    sources = get_sources()
    total_docs = collection.count()

    col_a, col_b = st.columns(2)
    col_a.metric("Chunks in DB", total_docs)
    col_b.metric("Source files", len(sources))  # bonus: unique source count
 
    st.divider()
 
    # Required: source filter
    selected_sources = st.multiselect(
        "Filter by source file",
        options=sources,
        help="Leave empty to search all files.",
    )
 
    n_results = st.slider("Results to show", 1, 10, 5)



# --- Main Search Interface ---
st.title("🔍 Semantic Search")
st.write("Search your course documents by meaning, not just keywords.")

query = st.text_input(
    "Enter your search query", 
    placeholder="How does data validation work?",
    key="query",
                      
)

if total_docs == 0:
    st.info("👈 Click 'Re-index Documents' in the sidebar to load your documents first.")

elif query:
    where = {"source": {"$in": selected_sources}} if selected_sources else None

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, total_docs),
        where=where,
    )

    shown = len(results["documents"][0])
    
    

    st.subheader(f"Showing {shown} of {total_docs} total documents")
    if selected_sources:
        st.caption(f"Filtered to: {', '.join(selected_sources)}")

    if shown == 0:
        st.warning("No results found.")

    for i in range(shown):
        doc = results["documents"][0][i]
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        with st.container():
            col_meta, col_score = st.columns([3, 1])
            with col_meta:
                st.write(f"**{metadata['source']}** — chunk {metadata['chunk_index']}")
            with col_score:
                st.write(f"{relevance_badge(distance)} (dist: {distance:.3f})")
 
            preview = doc[:150] + ("..." if len(doc) > 150 else "")
            st.write(preview)
            with st.expander("Show full chunk"):
                st.write(doc)


            st.button(
                "🔎 Similar to this",
                key=f"similar_{i}",
                on_click=set_query,
                args=(doc,),
            )
            st.divider()

