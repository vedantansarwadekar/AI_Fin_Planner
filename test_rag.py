from src.agents.rag_agent import StockMarketRAGAgent
import glob

if __name__ == "__main__":
    agent = StockMarketRAGAgent()

    pdfs = glob.glob("data/pdfs/*.pdf")
    print("PDFs found:", pdfs)

    result = agent.ingest_pdfs(pdfs)
    print("Ingestion result:", result)

    response = agent.ask("What are the powers of SEBI?")
    print("\nANSWER:\n", response["answer"])
    print("\nSOURCES:")
    for s in response["sources"]:
        print(s)
