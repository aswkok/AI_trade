import chromadb
from chromadb.config import Settings
from openai import OpenAI
import requests
import json
import os


class FinancialSituationMemory:
    def __init__(self, name, config):
        if config["backend_url"] == "http://localhost:11434/v1":
            self.embedding = "nomic-embed-text"
            self.client = OpenAI(base_url=config["backend_url"])
            self.use_hf_embeddings = False
        elif config["backend_url"] == "https://api.deepseek.com/v1":
            # DeepSeek doesn't support embeddings, use free Hugging Face embeddings
            self.embedding = "sentence-transformers/all-mpnet-base-v2"
            self.client = None
            self.use_hf_embeddings = True
        else:
            self.embedding = "text-embedding-3-small"
            self.client = OpenAI(base_url=config["backend_url"])
            self.use_hf_embeddings = False
        self.chroma_client = chromadb.Client(Settings(allow_reset=True))
        self.situation_collection = self.chroma_client.create_collection(name=name)

    def get_embedding(self, text):
        """Get embedding for a text using either OpenAI or Hugging Face"""
        
        if self.use_hf_embeddings:
            # Use Hugging Face Inference API (free)
            api_url = f"https://api-inference.huggingface.co/models/{self.embedding}"
            headers = {"Authorization": f"Bearer {os.getenv('HF_TOKEN', '')}"} if os.getenv('HF_TOKEN') else {}
            
            try:
                response = requests.post(api_url, headers=headers, json={"inputs": text})
                if response.status_code == 200:
                    return response.json()
                else:
                    # Fallback to local sentence-transformers if API fails
                    return self._get_local_embedding(text)
            except Exception as e:
                print(f"HF API error: {e}, falling back to local embedding")
                return self._get_local_embedding(text)
        else:
            # Use OpenAI or compatible API
            response = self.client.embeddings.create(
                model=self.embedding, input=text
            )
            return response.data[0].embedding

    def _get_local_embedding(self, text):
        """Fallback to local sentence-transformers model"""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
            return model.encode(text).tolist()
        except ImportError:
            print("sentence-transformers not installed. Install with: pip install sentence-transformers")
            # Return a dummy embedding as last resort
            return [0.0] * 768

    def add_situations(self, situations_and_advice):
        """Add financial situations and their corresponding advice. Parameter is a list of tuples (situation, rec)"""

        situations = []
        advice = []
        ids = []
        embeddings = []

        offset = self.situation_collection.count()

        for i, (situation, recommendation) in enumerate(situations_and_advice):
            situations.append(situation)
            advice.append(recommendation)
            ids.append(str(offset + i))
            embeddings.append(self.get_embedding(situation))

        self.situation_collection.add(
            documents=situations,
            metadatas=[{"recommendation": rec} for rec in advice],
            embeddings=embeddings,
            ids=ids,
        )

    def get_memories(self, current_situation, n_matches=1):
        """Find matching recommendations using OpenAI embeddings"""
        query_embedding = self.get_embedding(current_situation)

        results = self.situation_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_matches,
            include=["metadatas", "documents", "distances"],
        )

        matched_results = []
        for i in range(len(results["documents"][0])):
            matched_results.append(
                {
                    "matched_situation": results["documents"][0][i],
                    "recommendation": results["metadatas"][0][i]["recommendation"],
                    "similarity_score": 1 - results["distances"][0][i],
                }
            )

        return matched_results


if __name__ == "__main__":
    # Example usage
    matcher = FinancialSituationMemory()

    # Example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
        (
            "Market showing signs of sector rotation with rising yields",
            "Rebalance portfolio to maintain target allocations. Consider increasing exposure to sectors benefiting from higher rates.",
        ),
    ]

    # Add the example situations and recommendations
    matcher.add_situations(example_data)

    # Example query
    current_situation = """
    Market showing increased volatility in tech sector, with institutional investors 
    reducing positions and rising interest rates affecting growth stock valuations
    """

    try:
        recommendations = matcher.get_memories(current_situation, n_matches=2)

        for i, rec in enumerate(recommendations, 1):
            print(f"\nMatch {i}:")
            print(f"Similarity Score: {rec['similarity_score']:.2f}")
            print(f"Matched Situation: {rec['matched_situation']}")
            print(f"Recommendation: {rec['recommendation']}")

    except Exception as e:
        print(f"Error during recommendation: {str(e)}")
