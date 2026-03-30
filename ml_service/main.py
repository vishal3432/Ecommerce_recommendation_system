"""
FastAPI ML Service for Product Recommendations
- TF-IDF vectorization for content-based filtering
- Cosine similarity for recommendation scoring
- Async processing for better performance
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import asyncio
import logging
from datetime import datetime
import json
from dotenv import load_dotenv
import os
import redis
import httpx

load_dotenv()

app = FastAPI(title="ML Recommendation Engine", version="1.0.0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection for caching
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

# ==================== Models ====================

class Product(BaseModel):
    """Product data model"""
    id: int
    name: str
    description: str
    category: str
    tags: str = ""
    rating: float = 0.0


class RecommendationRequest(BaseModel):
    """Request model for recommendations"""
    user_id: int
    product_id: Optional[int] = None
    num_recommendations: int = Field(default=5, ge=1, le=50)
    browsing_history: List[int] = Field(default_factory=list)
    category_filter: Optional[str] = None
    task_id: Optional[str] = None


class RecommendationResponse(BaseModel):
    """Response model for recommendations"""
    status: str
    recommendations: List[Dict] = []
    task_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: str


class TrainingRequest(BaseModel):
    """Request to train/update embeddings"""
    products: List[Product]


# ==================== TF-IDF Vectorizer ====================

class RecommendationEngine:
    """Content-based recommendation engine using TF-IDF and Cosine Similarity"""
    
    def __init__(self):
        self.vectorizer = None
        self.tfidf_matrix = None
        self.products = {}
        self.product_ids = []
        
    def train(self, products: List[Product]):
        """
        Train the recommendation engine on product corpus
        
        Args:
            products: List of products with text data
        """
        try:
            logger.info(f"Starting training with {len(products)} products")
            
            # Store products
            self.products = {p.id: p for p in products}
            self.product_ids = [p.id for p in products]
            
            # Combine all text fields for each product
            corpus = [self._get_product_text(p) for p in products]
            
            # TF-IDF vectorization
            self.vectorizer = TfidfVectorizer(
                max_features=500,
                ngram_range=(1, 2),
                min_df=1,
                max_df=0.9,
                stop_words='english',
                lowercase=True,
                analyzer='word',
                token_pattern=r'\b[a-zA-Z]{2,}\b'
            )
            
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
            logger.info(f"Training complete. Matrix shape: {self.tfidf_matrix.shape}")
            
            # Cache training info
            redis_client.set('ml:model:trained', 'true', ex=86400*7)
            redis_client.set('ml:model:product_count', len(products), ex=86400*7)
            redis_client.set('ml:model:last_trained', datetime.now().isoformat(), ex=86400*7)
            
            return True
            
        except Exception as e:
            logger.error(f"Training error: {str(e)}")
            raise
    
    def _get_product_text(self, product: Product) -> str:
        """Combine all text fields for vectorization"""
        text_parts = [
            product.name,
            product.description,
            product.category,
            product.tags
        ]
        return " ".join(str(p) for p in text_parts if p)
    
    def get_recommendations(
        self, 
        product_id: int, 
        num_recommendations: int = 5,
        exclude_ids: List[int] = None,
        category_filter: str = None
    ) -> List[Dict]:
        """
        Get product recommendations based on similarity
        
        Args:
            product_id: Reference product ID
            num_recommendations: Number of recommendations to return
            exclude_ids: Product IDs to exclude
            category_filter: Filter by category
            
        Returns:
            List of recommended products with similarity scores
        """
        if not self.vectorizer or self.tfidf_matrix is None:
            raise ValueError("Model not trained yet")
        
        exclude_ids = exclude_ids or []
        
        try:
            # Find product index
            if product_id not in self.product_ids:
                return []
            
            product_idx = self.product_ids.index(product_id)
            
            # Calculate similarity with all products
            similarities = cosine_similarity(
                self.tfidf_matrix[product_idx],
                self.tfidf_matrix
            )[0]
            
            # Create recommendation list
            recommendations = []
            for idx, similarity in enumerate(similarities):
                pid = self.product_ids[idx]
                
                # Skip source product and excluded
                if pid == product_id or pid in exclude_ids:
                    continue
                
                product = self.products[pid]
                
                # Apply category filter if specified
                if category_filter and product.category != category_filter:
                    continue
                
                recommendations.append({
                    'id': pid,
                    'name': product.name,
                    'similarity_score': float(similarity),
                    'category': product.category,
                    'rating': product.rating
                })
            
            # Sort by similarity and return top-N
            recommendations.sort(key=lambda x: x['similarity_score'], reverse=True)
            return recommendations[:num_recommendations]
            
        except Exception as e:
            logger.error(f"Recommendation error: {str(e)}")
            return []
    
    def get_personalized_recommendations(
        self,
        browsing_history: List[int],
        num_recommendations: int = 5,
        exclude_ids: List[int] = None
    ) -> List[Dict]:
        """
        Get personalized recommendations based on browsing history
        
        Args:
            browsing_history: List of product IDs user viewed
            num_recommendations: Number of recommendations
            exclude_ids: Products to exclude
            
        Returns:
            Aggregated recommendations from browsing history
        """
        if not browsing_history or not self.tfidf_matrix is not None:
            return []
        
        exclude_ids = exclude_ids or []
        
        try:
            # Get valid product indices from history
            history_indices = [
                self.product_ids.index(pid) 
                for pid in browsing_history 
                if pid in self.product_ids
            ]
            
            if not history_indices:
                return []
            
            # Calculate average similarity from browsing history
            all_similarities = np.zeros(len(self.product_ids))
            
            for idx in history_indices:
                similarities = cosine_similarity(
                    self.tfidf_matrix[idx],
                    self.tfidf_matrix
                )[0]
                all_similarities += similarities
            
            # Average and normalize
            all_similarities /= len(history_indices)
            
            # Create recommendations
            recommendations = []
            for idx, similarity in enumerate(all_similarities):
                pid = self.product_ids[idx]
                
                if pid in browsing_history or pid in exclude_ids:
                    continue
                
                product = self.products[pid]
                recommendations.append({
                    'id': pid,
                    'name': product.name,
                    'similarity_score': float(similarity),
                    'category': product.category,
                    'rating': product.rating
                })
            
            recommendations.sort(key=lambda x: x['similarity_score'], reverse=True)
            return recommendations[:num_recommendations]
            
        except Exception as e:
            logger.error(f"Personalized recommendation error: {str(e)}")
            return []


# Initialize engine
recommendation_engine = RecommendationEngine()

# ==================== API Endpoints ====================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("ML Service started")
    # Load cached model if available
    is_trained = redis_client.get('ml:model:trained')
    if is_trained:
        logger.info("Model state cached")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ML Recommendation Engine",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/train")
async def train_model(request: TrainingRequest, background_tasks: BackgroundTasks):
    """
    Train the recommendation model
    
    Args:
        request: Products to train on
    """
    try:
        background_tasks.add_task(recommendation_engine.train, request.products)
        return {
            "status": "training_started",
            "product_count": len(request.products),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Training endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend")
async def get_recommendations(request: RecommendationRequest):
    """
    Get product recommendations
    
    Args:
        request: Recommendation request parameters
    """
    try:
        # Check if model is trained
        if recommendation_engine.tfidf_matrix is None:
            return RecommendationResponse(
                status="error",
                error="Model not trained yet",
                task_id=request.task_id
            )
        
        # Get recommendations
        if request.product_id:
            # Content-based from single product
            recommendations = recommendation_engine.get_recommendations(
                product_id=request.product_id,
                num_recommendations=request.num_recommendations,
                exclude_ids=request.browsing_history,
                category_filter=request.category_filter
            )
        elif request.browsing_history:
            # Personalized from history
            recommendations = recommendation_engine.get_personalized_recommendations(
                browsing_history=request.browsing_history,
                num_recommendations=request.num_recommendations,
                exclude_ids=request.browsing_history
            )
        else:
            recommendations = []
        
        # Update task status in Django
        if request.task_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{os.getenv('DJANGO_SERVICE_URL', 'http://localhost:8000')}/api/tasks/{request.task_id}/update/",
                        json={
                            'status': 'completed',
                            'recommendations': [r['id'] for r in recommendations]
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to update task status: {str(e)}")
        
        return RecommendationResponse(
            status="success",
            recommendations=recommendations,
            task_id=request.task_id,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Recommendation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend/batch")
async def batch_recommendations(requests: List[RecommendationRequest]):
    """
    Get recommendations for multiple users/products
    
    Args:
        requests: List of recommendation requests
    """
    try:
        results = []
        for req in requests:
            if req.product_id:
                recs = recommendation_engine.get_recommendations(
                    product_id=req.product_id,
                    num_recommendations=req.num_recommendations,
                    exclude_ids=req.browsing_history,
                    category_filter=req.category_filter
                )
            elif req.browsing_history:
                recs = recommendation_engine.get_personalized_recommendations(
                    browsing_history=req.browsing_history,
                    num_recommendations=req.num_recommendations,
                    exclude_ids=req.browsing_history
                )
            else:
                recs = []
            
            results.append({
                'user_id': req.user_id,
                'recommendations': recs
            })
        
        return {
            'status': 'success',
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch recommendation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/model/info")
async def model_info():
    """Get information about trained model"""
    return {
        "trained": recommendation_engine.tfidf_matrix is not None,
        "product_count": len(recommendation_engine.products),
        "matrix_shape": list(recommendation_engine.tfidf_matrix.shape) if recommendation_engine.tfidf_matrix is not None else None,
        "vectorizer_features": recommendation_engine.vectorizer.n_features_ if recommendation_engine.vectorizer else 0,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
