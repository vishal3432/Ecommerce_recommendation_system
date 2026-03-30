"""
Comprehensive ML Model Testing Suite
- Unit tests for recommendation engine
- Integration tests
- Metric evaluation tests
"""

import unittest
import numpy as np
from typing import List
import json
from unittest.mock import Mock, patch, MagicMock

# Import from ML service
import sys
sys.path.insert(0, 'ml_service')

from ml_service.main import RecommendationEngine, recommendation_engine
from ml_service.metrics import (
    RecommendationMetrics, SemanticMetrics, ModelEvaluator,
    EvaluationMetrics
)


class TestTFIDFVectorizer(unittest.TestCase):
    """Test TF-IDF vectorization and training"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = RecommendationEngine()
        self.test_products = [
            Mock(
                id=1,
                name="Laptop Computer",
                description="High-performance laptop for gaming",
                category="Electronics",
                tags="gaming,computer,portable",
                rating=4.5
            ),
            Mock(
                id=2,
                name="Gaming Mouse",
                description="Professional gaming mouse with high precision",
                category="Electronics",
                tags="gaming,mouse,accessories",
                rating=4.2
            ),
            Mock(
                id=3,
                name="Mechanical Keyboard",
                description="RGB mechanical keyboard for gaming and work",
                category="Electronics",
                tags="gaming,keyboard,mechanical",
                rating=4.8
            ),
            Mock(
                id=4,
                name="Coffee Maker",
                description="Automatic coffee maker for morning brew",
                category="Appliances",
                tags="coffee,kitchen,appliance",
                rating=3.9
            ),
        ]
    
    def test_training(self):
        """Test model training"""
        self.engine.train(self.test_products)
        
        # Assertions
        self.assertIsNotNone(self.engine.vectorizer)
        self.assertIsNotNone(self.engine.tfidf_matrix)
        self.assertEqual(len(self.engine.products), 4)
        self.assertEqual(self.engine.tfidf_matrix.shape[0], 4)
    
    def test_product_text_combination(self):
        """Test text field combination"""
        product = self.test_products[0]
        text = self.engine._get_product_text(product)
        
        self.assertIn("Laptop", text)
        self.assertIn("gaming", text)
        self.assertIn("Electronics", text)
    
    def test_vector_sparsity(self):
        """Test that TF-IDF matrix is sparse"""
        self.engine.train(self.test_products)
        
        sparsity = 1 - (self.engine.tfidf_matrix.nnz /
                        (self.engine.tfidf_matrix.shape[0] *
                         self.engine.tfidf_matrix.shape[1]))
        
        # TF-IDF should create sparse vectors
        self.assertGreater(sparsity, 0.5)


class TestCosineSimilarity(unittest.TestCase):
    """Test cosine similarity-based recommendations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = RecommendationEngine()
        self.test_products = [
            Mock(
                id=1,
                name="iPhone 15",
                description="Latest iPhone with advanced camera",
                category="Smartphones",
                tags="phone,apple,smartphone",
                rating=4.8
            ),
            Mock(
                id=2,
                name="iPhone 14",
                description="Previous iPhone model",
                category="Smartphones",
                tags="phone,apple,smartphone",
                rating=4.6
            ),
            Mock(
                id=3,
                name="Samsung Galaxy",
                description="Premium Samsung smartphone",
                category="Smartphones",
                tags="phone,samsung,smartphone",
                rating=4.5
            ),
            Mock(
                id=4,
                name="USB-C Cable",
                description="High-quality USB-C charging cable",
                category="Accessories",
                tags="cable,charger,usb",
                rating=4.2
            ),
        ]
        self.engine.train(self.test_products)
    
    def test_similar_products_recommendation(self):
        """Test recommendation of similar products"""
        recommendations = self.engine.get_recommendations(
            product_id=1,
            num_recommendations=2
        )
        
        self.assertEqual(len(recommendations), 2)
        # iPhone should be recommended with similar products
        self.assertIn(recommendations[0]['id'], [2, 3])
    
    def test_similarity_score_range(self):
        """Test that similarity scores are in valid range"""
        recommendations = self.engine.get_recommendations(
            product_id=1,
            num_recommendations=3
        )
        
        for rec in recommendations:
            self.assertGreaterEqual(rec['similarity_score'], 0)
            self.assertLessEqual(rec['similarity_score'], 1)
    
    def test_exclude_products(self):
        """Test excluding specific products"""
        recommendations = self.engine.get_recommendations(
            product_id=1,
            num_recommendations=5,
            exclude_ids=[2, 3]
        )
        
        recommended_ids = [r['id'] for r in recommendations]
        self.assertNotIn(2, recommended_ids)
        self.assertNotIn(3, recommended_ids)
    
    def test_category_filter(self):
        """Test category filtering"""
        recommendations = self.engine.get_recommendations(
            product_id=1,
            num_recommendations=5,
            category_filter='Smartphones'
        )
        
        for rec in recommendations:
            self.assertEqual(rec['category'], 'Smartphones')


class TestPersonalizedRecommendations(unittest.TestCase):
    """Test personalized recommendations from browsing history"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = RecommendationEngine()
        self.test_products = [
            Mock(id=i, name=f"Product {i}", description=f"Description {i}",
                 category=f"Category {i%3}", tags="tag", rating=4.0)
            for i in range(1, 11)
        ]
        self.engine.train(self.test_products)
    
    def test_personalized_from_history(self):
        """Test personalized recommendations from browsing history"""
        browsing_history = [1, 2, 3]
        
        recommendations = self.engine.get_personalized_recommendations(
            browsing_history=browsing_history,
            num_recommendations=3
        )
        
        self.assertEqual(len(recommendations), 3)
        # Recommendations should not be in history
        rec_ids = [r['id'] for r in recommendations]
        self.assertNotIn(1, rec_ids)
        self.assertNotIn(2, rec_ids)
        self.assertNotIn(3, rec_ids)
    
    def test_empty_history(self):
        """Test with empty browsing history"""
        recommendations = self.engine.get_personalized_recommendations(
            browsing_history=[],
            num_recommendations=5
        )
        
        self.assertEqual(len(recommendations), 0)


class TestRecommendationMetrics(unittest.TestCase):
    """Test recommendation quality metrics"""
    
    def test_precision_at_k(self):
        """Test Precision@K metric"""
        metrics = RecommendationMetrics()
        
        predictions = [1, 2, 3, 4, 5]
        ground_truth = [1, 2, 6, 7, 8]
        
        precision = metrics.precision_at_k(predictions, ground_truth, k=5)
        
        self.assertEqual(precision, 0.4)  # 2/5
    
    def test_recall_at_k(self):
        """Test Recall@K metric"""
        metrics = RecommendationMetrics()
        
        predictions = [1, 2, 3, 4, 5]
        ground_truth = [1, 2, 6, 7]
        
        recall = metrics.recall_at_k(predictions, ground_truth, k=5)
        
        self.assertEqual(recall, 0.5)  # 2/4
    
    def test_ndcg_at_k(self):
        """Test NDCG@K metric"""
        metrics = RecommendationMetrics()
        
        predictions = [(1, 1.0), (2, 0.9), (3, 0.8), (4, 0.7), (5, 0.6)]
        ground_truth = [1, 2, 3]
        
        ndcg = metrics.ndcg_at_k(predictions, ground_truth, k=5)
        
        self.assertGreater(ndcg, 0)
        self.assertLessEqual(ndcg, 1)
    
    def test_coverage(self):
        """Test coverage metric"""
        metrics = RecommendationMetrics()
        
        predictions = [[1, 2], [2, 3], [4, 5]]
        total_items = 10
        
        coverage = metrics.coverage(predictions, total_items)
        
        self.assertEqual(coverage, 0.5)  # 5/10
    
    def test_diversity(self):
        """Test diversity metric"""
        metrics = RecommendationMetrics()
        
        # Create simple similarity matrix
        similarity_matrix = np.array([
            [1.0, 0.9, 0.1, 0.2],
            [0.9, 1.0, 0.2, 0.1],
            [0.1, 0.2, 1.0, 0.8],
            [0.2, 0.1, 0.8, 1.0],
        ])
        
        predictions = [0, 2]  # Very different items
        diversity = metrics.diversity(predictions, similarity_matrix)
        
        # Dissimilarity should be high
        self.assertGreater(diversity, 0.7)


class TestSemanticMetrics(unittest.TestCase):
    """Test semantic similarity metrics"""
    
    def test_rouge_score_calculation(self):
        """Test ROUGE score calculation"""
        semantic = SemanticMetrics()
        
        reference = "The quick brown fox jumps over the lazy dog"
        generated = "The fast brown fox jumps over the lazy dog"
        
        scores = semantic.rouge_score(reference, generated)
        
        self.assertIn('rouge1', scores)
        self.assertIn('rouge2', scores)
        self.assertIn('rougeL', scores)
        self.assertGreater(scores['rouge1'], 0.5)


class TestModelEvaluator(unittest.TestCase):
    """Test comprehensive model evaluation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.evaluator = ModelEvaluator()
        self.similarity_matrix = np.random.rand(10, 10)
        # Make symmetric
        self.similarity_matrix = (self.similarity_matrix + self.similarity_matrix.T) / 2
    
    def test_batch_evaluation(self):
        """Test batch evaluation across multiple users"""
        predictions = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        ground_truth = [[1, 2], [4, 5], [7, 8]]
        
        results = self.evaluator.batch_evaluate(
            predictions, ground_truth,
            self.similarity_matrix,
            total_items=10,
            k=3
        )
        
        self.assertIn('mean_precision', results)
        self.assertIn('mean_recall', results)
        self.assertIn('mean_ndcg', results)
        self.assertGreater(results['evaluation_count'], 0)


class TestIntegration(unittest.TestCase):
    """Integration tests for full recommendation pipeline"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = RecommendationEngine()
        self.products = [
            Mock(
                id=i,
                name=f"Product {i}",
                description=f"This is product {i} with description",
                category=f"Category {i % 3}",
                tags=f"tag{i}",
                rating=np.random.uniform(3, 5)
            )
            for i in range(1, 21)
        ]
    
    def test_full_pipeline(self):
        """Test full recommendation pipeline"""
        # Train
        self.engine.train(self.products)
        
        # Generate recommendations
        recommendations = self.engine.get_recommendations(
            product_id=1,
            num_recommendations=5
        )
        
        # Verify
        self.assertEqual(len(recommendations), 5)
        for rec in recommendations:
            self.assertIn('id', rec)
            self.assertIn('similarity_score', rec)
            self.assertIn('name', rec)
    
    def test_personalized_pipeline(self):
        """Test full personalized recommendation pipeline"""
        # Train
        self.engine.train(self.products)
        
        # Simulate browsing history
        browsing_history = [1, 2, 3, 4, 5]
        
        # Generate personalized recommendations
        recommendations = self.engine.get_personalized_recommendations(
            browsing_history=browsing_history,
            num_recommendations=5
        )
        
        # Verify
        self.assertLessEqual(len(recommendations), 5)
        rec_ids = [r['id'] for r in recommendations]
        
        # Should not recommend browsed products
        for history_id in browsing_history:
            self.assertNotIn(history_id, rec_ids)


# Test runner
if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all tests
    suite.addTests(loader.loadTestsFromTestCase(TestTFIDFVectorizer))
    suite.addTests(loader.loadTestsFromTestCase(TestCosineSimilarity))
    suite.addTests(loader.loadTestsFromTestCase(TestPersonalizedRecommendations))
    suite.addTests(loader.loadTestsFromTestCase(TestRecommendationMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestSemanticMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestModelEvaluator))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*70)
