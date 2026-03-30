from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class Category(models.Model):
    """Product Category Model"""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Product Model with embeddings for recommendations"""
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.IntegerField(validators=[MinValueValidator(0)])
    rating = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    image_url = models.URLField(blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    
    # ML fields
    tfidf_vector = models.JSONField(default=dict, blank=True, help_text="Stored TF-IDF vector")
    embedding_updated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def full_text(self):
        """Combine all text fields for TF-IDF vectorization"""
        return f"{self.name} {self.description} {self.tags} {self.category.name}"


class UserProfile(models.Model):
    """Extended user profile for preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    preferences = models.JSONField(default=dict, help_text="User preference data")
    browsing_history = models.JSONField(default=list, help_text="Product IDs viewed by user")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} Profile"
    
    def add_to_browsing_history(self, product_id):
        """Add product to browsing history (keep last 100)"""
        if product_id not in self.browsing_history:
            self.browsing_history.append(product_id)
        if len(self.browsing_history) > 100:
            self.browsing_history = self.browsing_history[-100:]
        self.save()


class Review(models.Model):
    """Product reviews for user interaction"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('product', 'user')
    
    def __str__(self):
        return f"Review by {self.user.username} for {self.product.name}"


class RecommendationTask(models.Model):
    """Track recommendation generation tasks"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendation_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    recommendations = models.JSONField(default=list, help_text="List of recommended product IDs")
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['task_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Task {self.task_id} - {self.status}"


class UserBehavior(models.Model):
    """Track user interactions for ML model training"""
    EVENT_CHOICES = [
        ('view', 'Product View'),
        ('click', 'Product Click'),
        ('cart', 'Add to Cart'),
        ('purchase', 'Purchase'),
        ('review', 'Review Left'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='behaviors')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='user_behaviors')
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['product', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.event_type} - {self.product.name}"
