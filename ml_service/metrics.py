"""
ML Model Evaluation Metrics
- BERT Score for semantic similarity
- ROUGE Score for content coverage
- Perplexity for language model evaluation
- Custom recommendation metrics
"""

import numpy as np
from typing import List, Dict, Tuple
import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    """Container for evaluation metrics"""
    bert_score: float
    rouge_1: float
    rouge_2: float
    rouge_l: float
    perplexity: float
    precision_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    coverage: float
    diversity: float
    timestamp: str
    
    def to_dict(self):
        return asdict(self)
    
    def __str__(self):
        return json.dumps(self.to_dict(), indent=2)


class RecommendationMetrics:
    """Calculate recommendation system metrics"""
    
    @staticmethod
    def precision_at_k(predictions: List[int], ground_truth: List[int], k: int = 5) -> float:
        """
        Precision@K: What fraction of top-k predictions are relevant?
        
        Args:
            predictions: Predicted product IDs (ranked)
            ground_truth: Relevant product IDs
            k: Number of top predictions to consider
            
        Returns:
            Precision@K score (0-1)
        """
        if not predictions or k == 0:
            return 0.0
        
        relevant = len(set(predictions[:k]) & set(ground_truth))
        return relevant / min(k, len(predictions))
    
    @staticmethod
    def recall_at_k(predictions: List[int], ground_truth: List[int], k: int = 5) -> float:
        """
        Recall@K: What fraction of all relevant items are in top-k?
        
        Args:
            predictions: Predicted product IDs (ranked)
            ground_truth: Relevant product IDs
            k: Number of top predictions to consider
            
        Returns:
            Recall@K score (0-1)
        """
        if not ground_truth:
            return 0.0
        
        relevant = len(set(predictions[:k]) & set(ground_truth))
        return relevant / len(ground_truth)
    
    @staticmethod
    def ndcg_at_k(predictions: List[Tuple[int, float]], ground_truth: List[int], k: int = 5) -> float:
        """
        Normalized Discounted Cumulative Gain@K
        Measures ranking quality, giving higher weight to items ranked better
        
        Args:
            predictions: List of (product_id, score) tuples ranked by score
            ground_truth: Relevant product IDs
            k: Number of top predictions to consider
            
        Returns:
            NDCG@K score (0-1)
        """
        if not ground_truth or not predictions:
            return 0.0
        
        # DCG
        dcg = 0.0
        for i, (pred_id, score) in enumerate(predictions[:k]):
            if pred_id in ground_truth:
                dcg += 1.0 / np.log2(i + 2)  # i+2 because ranking is 1-indexed
        
        # IDCG (ideal DCG)
        idcg = 0.0
        for i in range(min(k, len(ground_truth))):
            idcg += 1.0 / np.log2(i + 2)
        
        return dcg / idcg if idcg > 0 else 0.0
    
    @staticmethod
    def coverage(predictions: List[List[int]], total_items: int) -> float:
        """
        Coverage: What fraction of all items appear in recommendations?
        
        Args:
            predictions: List of recommendation lists for multiple users
            total_items: Total number of items in catalog
            
        Returns:
            Coverage score (0-1)
        """
        if not predictions or total_items == 0:
            return 0.0
        
        unique_items = len(set(item for sublist in predictions for item in sublist))
        return unique_items / total_items
    
    @staticmethod
    def diversity(predictions: List[int], similarity_matrix: np.ndarray) -> float:
        """
        Diversity: Average dissimilarity between recommended items
        
        Args:
            predictions: Recommended product IDs
            similarity_matrix: NxN similarity matrix between all products
            
        Returns:
            Diversity score (0-1, where 0=identical, 1=completely different)
        """
        if len(predictions) < 2:
            return 1.0
        
        # Calculate average pairwise dissimilarity
        dissimilarities = []
        for i in range(len(predictions)):
            for j in range(i + 1, len(predictions)):
                dissim = 1 - similarity_matrix[predictions[i]][predictions[j]]
                dissimilarities.append(dissim)
        
        return np.mean(dissimilarities) if dissimilarities else 0.0


class SemanticMetrics:
    """Metrics for semantic similarity and text evaluation"""
    
    @staticmethod
    def bert_score(reference_texts: List[str], generated_texts: List[str]) -> Dict[str, float]:
        """
        BERT Score using sentence transformers
        Measures semantic similarity between texts using BERT embeddings
        
        Args:
            reference_texts: Ground truth texts
            generated_texts: Generated/predicted texts
            
        Returns:
            Dict with precision, recall, f1 scores
        """
        try:
            from sentence_transformers import SentenceTransformer, util
            
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            ref_embeddings = model.encode(reference_texts, convert_to_tensor=True)
            gen_embeddings = model.encode(generated_texts, convert_to_tensor=True)
            
            # Calculate cosine similarities
            cosine_scores = util.pytorch_cos_sim(gen_embeddings, ref_embeddings)
            
            precision = float(cosine_scores.max(dim=1)[0].mean().item())
            recall = float(cosine_scores.max(dim=0)[0].mean().item())
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            return {
                'precision': precision,
                'recall': recall,
                'f1': f1
            }
        except ImportError:
            logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")
            return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}
        except Exception as e:
            logger.error(f"BERT Score error: {str(e)}")
            return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}
    
    @staticmethod
    def rouge_score(reference: str, generated: str) -> Dict[str, float]:
        """
        ROUGE Score (Recall-Oriented Understudy for Gisting Evaluation)
        Measures overlap of n-grams between reference and generated text
        
        Args:
            reference: Reference text
            generated: Generated text
            
        Returns:
            Dict with ROUGE-1, ROUGE-2, ROUGE-L scores
        """
        try:
            from rouge_score import rouge_scorer
            
            scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
            scores = scorer.score(reference, generated)
            
            return {
                'rouge1': scores['rouge1'].fmeasure,
                'rouge2': scores['rouge2'].fmeasure,
                'rougeL': scores['rougeL'].fmeasure
            }
        except ImportError:
            logger.warning("rouge-score not installed. Install with: pip install rouge-score")
            return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}
        except Exception as e:
            logger.error(f"ROUGE Score error: {str(e)}")
            return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}
    
    @staticmethod
    def perplexity(text: str, model_name: str = 'gpt2') -> float:
        """
        Perplexity: How surprised is the model by the text?
        Lower perplexity = model thinks text is more natural
        
        Args:
            text: Text to evaluate
            model_name: HuggingFace model to use
            
        Returns:
            Perplexity score
        """
        try:
            import torch
            from transformers import GPT2Tokenizer, GPT2LMHeadModel
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = GPT2LMHeadModel.from_pretrained(model_name).to(device)
            tokenizer = GPT2Tokenizer.from_pretrained(model_name)
            
            # Tokenize
            encoded = tokenizer.encode(text, return_tensors='pt').to(device)
            
            if encoded.shape[1] == 0:
                return float('inf')
            
            # Calculate perplexity
            with torch.no_grad():
                outputs = model(encoded, labels=encoded)
                loss = outputs.loss
            
            perplexity = torch.exp(loss).item()
            return perplexity
            
        except ImportError:
            logger.warning("transformers not installed. Install with: pip install transformers torch")
            return 0.0
        except Exception as e:
            logger.error(f"Perplexity calculation error: {str(e)}")
            return 0.0


class ModelEvaluator:
    """Comprehensive model evaluation"""
    
    @staticmethod
    def evaluate_recommendations(
        predictions: List[int],
        ground_truth: List[int],
        similarity_matrix: np.ndarray,
        all_predictions: List[List[int]] = None,
        total_items: int = None,
        k: int = 5
    ) -> EvaluationMetrics:
        """
        Comprehensive evaluation of recommendation system
        
        Args:
            predictions: Predicted items for a user (ranked)
            ground_truth: Relevant items for the user
            similarity_matrix: Item similarity matrix
            all_predictions: All predictions (for coverage)
            total_items: Total number of items
            k: Cutoff for @k metrics
            
        Returns:
            EvaluationMetrics object
        """
        metrics = RecommendationMetrics()
        semantic = SemanticMetrics()
        
        # Ranking metrics
        precision = metrics.precision_at_k(predictions, ground_truth, k)
        recall = metrics.recall_at_k(predictions, ground_truth, k)
        
        # NDCG (convert to tuples with dummy scores)
        pred_tuples = [(p, 1.0 - i/len(predictions)) for i, p in enumerate(predictions)]
        ndcg = metrics.ndcg_at_k(pred_tuples, ground_truth, k)
        
        # Coverage and diversity
        coverage = metrics.coverage(all_predictions, total_items) if all_predictions and total_items else 0.0
        diversity = metrics.diversity(predictions[:k], similarity_matrix) if len(predictions) > 1 else 1.0
        
        # Default semantic metrics (mock data)
        bert_f1 = 0.0  # Would need actual text comparison
        rouge_1 = 0.0
        rouge_2 = 0.0
        rouge_l = 0.0
        perplexity = 0.0
        
        return EvaluationMetrics(
            bert_score=bert_f1,
            rouge_1=rouge_1,
            rouge_2=rouge_2,
            rouge_l=rouge_l,
            perplexity=perplexity,
            precision_at_k=precision,
            recall_at_k=recall,
            ndcg_at_k=ndcg,
            coverage=coverage,
            diversity=diversity,
            timestamp=datetime.now().isoformat()
        )
    
    @staticmethod
    def batch_evaluate(
        all_predictions: List[List[int]],
        all_ground_truth: List[List[int]],
        similarity_matrix: np.ndarray,
        total_items: int,
        k: int = 5
    ) -> Dict:
        """
        Evaluate across multiple users
        
        Returns:
            Aggregated metrics
        """
        metrics_list = []
        
        for predictions, ground_truth in zip(all_predictions, all_ground_truth):
            m = ModelEvaluator.evaluate_recommendations(
                predictions,
                ground_truth,
                similarity_matrix,
                all_predictions,
                total_items,
                k
            )
            metrics_list.append(m)
        
        # Aggregate
        return {
            'mean_precision': np.mean([m.precision_at_k for m in metrics_list]),
            'mean_recall': np.mean([m.recall_at_k for m in metrics_list]),
            'mean_ndcg': np.mean([m.ndcg_at_k for m in metrics_list]),
            'mean_diversity': np.mean([m.diversity for m in metrics_list]),
            'overall_coverage': metrics_list[0].coverage if metrics_list else 0.0,
            'evaluation_count': len(metrics_list),
            'timestamp': datetime.now().isoformat()
        }
