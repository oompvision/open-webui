"""
Mentor RAG Service for AlumniHuddle

This service manages the RAG (Retrieval Augmented Generation) knowledge base
for mentor profiles. Each huddle has its own collection of mentor documents
that the AI can search to make recommendations.
"""

import logging
from typing import Optional, List

from open_webui.models.mentors import Mentors, MentorProfileModel
from open_webui.models.tenants import Huddles
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT

log = logging.getLogger(__name__)


def get_mentor_collection_name(huddle_id: str) -> str:
    """
    Get the vector DB collection name for a huddle's mentors.
    Each huddle has its own isolated collection.
    """
    return f"mentors-{huddle_id}"


class MentorRAGService:
    """
    Service for managing mentor profiles in the RAG system.

    This creates and maintains vector embeddings of mentor profiles
    that the AI can search to find relevant mentors for users.
    """

    def __init__(self, embedding_function=None):
        """
        Initialize the service.

        Args:
            embedding_function: Async function to generate embeddings.
                               Should be request.app.state.EMBEDDING_FUNCTION
        """
        self.embedding_function = embedding_function

    async def index_mentor(
        self,
        mentor: MentorProfileModel,
    ) -> bool:
        """
        Index a single mentor profile in the vector database.

        Args:
            mentor: The mentor profile to index

        Returns:
            True if successful, False otherwise
        """
        if not self.embedding_function:
            log.error("Embedding function not set")
            return False

        try:
            collection_name = get_mentor_collection_name(mentor.huddle_id)
            document_text = mentor.to_rag_document()

            # Generate embedding
            embedding = await self.embedding_function(document_text)

            # Upsert to vector DB
            VECTOR_DB_CLIENT.upsert(
                collection_name=collection_name,
                items=[
                    {
                        "id": mentor.id,
                        "text": document_text,
                        "vector": embedding,
                        "metadata": {
                            "mentor_id": mentor.id,
                            "huddle_id": mentor.huddle_id,
                            "full_name": mentor.full_name,
                            "title": mentor.title or "",
                            "company": mentor.current_company or "",
                            "industry": mentor.industry or "",
                            "class_year": str(mentor.class_year),
                        },
                    }
                ],
            )

            log.info(f"Indexed mentor: {mentor.full_name} ({mentor.id})")
            return True

        except Exception as e:
            log.error(f"Failed to index mentor {mentor.id}: {e}")
            return False

    async def index_all_mentors_for_huddle(
        self,
        huddle_id: str,
    ) -> dict:
        """
        Index all mentors for a specific huddle.

        Args:
            huddle_id: The huddle ID to index mentors for

        Returns:
            Dict with counts: {"indexed": N, "failed": N, "total": N}
        """
        mentors = Mentors.get_mentors_by_huddle(huddle_id, limit=1000)

        results = {"indexed": 0, "failed": 0, "total": len(mentors)}

        for mentor in mentors:
            success = await self.index_mentor(mentor)
            if success:
                results["indexed"] += 1
            else:
                results["failed"] += 1

        log.info(f"Indexed {results['indexed']}/{results['total']} mentors for huddle {huddle_id}")
        return results

    async def index_all_mentors(self) -> dict:
        """
        Index all mentors across all huddles.

        Returns:
            Dict with results per huddle
        """
        huddle_ids = Mentors.get_all_huddle_ids_with_mentors()
        results = {}

        for huddle_id in huddle_ids:
            huddle = Huddles.get_huddle_by_id(huddle_id)
            huddle_name = huddle.name if huddle else huddle_id

            result = await self.index_all_mentors_for_huddle(huddle_id)
            results[huddle_name] = result

        return results

    def remove_mentor(self, mentor_id: str, huddle_id: str) -> bool:
        """
        Remove a mentor from the vector database.

        Args:
            mentor_id: The mentor's ID
            huddle_id: The huddle's ID

        Returns:
            True if successful, False otherwise
        """
        try:
            collection_name = get_mentor_collection_name(huddle_id)
            VECTOR_DB_CLIENT.delete(
                collection_name=collection_name,
                ids=[mentor_id],
            )
            log.info(f"Removed mentor {mentor_id} from index")
            return True
        except Exception as e:
            log.error(f"Failed to remove mentor {mentor_id}: {e}")
            return False

    async def search_mentors(
        self,
        huddle_id: str,
        query: str,
        limit: int = 5,
    ) -> List[dict]:
        """
        Search for mentors matching a query within a specific huddle.

        Args:
            huddle_id: The huddle to search within
            query: The search query (e.g., "finance experience in NYC")
            limit: Maximum number of results

        Returns:
            List of search results with mentor info and relevance scores
        """
        if not self.embedding_function:
            log.error("Embedding function not set")
            return []

        try:
            collection_name = get_mentor_collection_name(huddle_id)

            # Check if collection exists
            if not VECTOR_DB_CLIENT.has_collection(collection_name):
                log.warning(f"No mentor collection for huddle {huddle_id}")
                return []

            # Generate query embedding
            query_embedding = await self.embedding_function(query)

            # Search vector DB
            results = VECTOR_DB_CLIENT.search(
                collection_name=collection_name,
                vectors=[query_embedding],
                limit=limit,
            )

            if not results or not results.ids:
                return []

            # Format results
            search_results = []
            for i, mentor_id in enumerate(results.ids[0]):
                # Get full mentor profile
                mentor = Mentors.get_mentor_by_id(mentor_id)
                if mentor:
                    search_results.append({
                        "mentor": mentor.model_dump(),
                        "relevance_score": results.distances[0][i] if results.distances else 0,
                        "document_text": results.documents[0][i] if results.documents else "",
                    })

            return search_results

        except Exception as e:
            log.error(f"Failed to search mentors: {e}")
            return []

    def get_collection_stats(self, huddle_id: str) -> dict:
        """
        Get statistics about a huddle's mentor collection.

        Returns:
            Dict with collection stats
        """
        try:
            collection_name = get_mentor_collection_name(huddle_id)

            if not VECTOR_DB_CLIENT.has_collection(collection_name):
                return {"exists": False, "count": 0}

            # Get collection info
            result = VECTOR_DB_CLIENT.get(collection_name=collection_name)
            count = len(result.ids) if result and result.ids else 0

            return {"exists": True, "count": count}

        except Exception as e:
            log.error(f"Failed to get collection stats: {e}")
            return {"exists": False, "count": 0, "error": str(e)}


# Note: The embedding function needs to be set from the request context
# Usage:
#   service = MentorRAGService(request.app.state.EMBEDDING_FUNCTION)
#   await service.index_all_mentors_for_huddle(huddle_id)
