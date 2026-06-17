
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer


model_name = "BAAI/bge-m3"
tokenizer = AutoTokenizer.from_pretrained(model_name)

def bge_m3_token_len(text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))  

def bge_m3_tokenize(text: str):
    return tokenizer.encode(text, add_special_tokens=False)

def chunk_award(award: dict, chunk_size: int = 1400, overlap: int = 50):
    header = f"""Title: {award['title']}
PI: {award['pi_name']}
Agency: {award['agency']}
Institution: {award['institution']}
Directorate: {award['program_directorate']}
Year: {award['award_year']}
Amount: {award['amount']}"""
    abstract = award["abstract"].replace(
    "This award reflects NSF's statutory mission and has been deemed worthy of support through evaluation using the Foundation's intellectual merit and broader impacts review criteria.",
    "").strip()

    header_len = bge_m3_token_len(header)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size - header_len,
        chunk_overlap=overlap,
        length_function=bge_m3_token_len,
        separators=[]
    )

    chunks = text_splitter.split_text(abstract)

    return [{
        "id": f"chunk-{award["award_id"]}-{chunk_i}",
        'metadata': {
            "award_id": award["award_id"],
            "domain": award["domain"],
            "chunk_index": chunk_i,
            "source": award["agency"],
            "title": award["title"],
            "pi_name": award["pi_name"],
            "institution": award["institution"],
            "directorate": award["program_directorate"],
            "year": award["award_year"],
            "amount": award["amount"]
        },
        'text': f"Header: {header}\n\nAbstract: {chunks[chunk_i]}"
        } for chunk_i in range(len(chunks))]
