"""
Django REST Framework Serializers
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from ecommerce.models import (
    Product, Category, Review, RecommendationTask,
    UserProfile, UserBehavior
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'created_at']
        read_only_fields = ['created_at']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    review_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'category', 'category_name',
            'price', 'stock', 'rating', 'average_rating', 'review_count',
            'image_url', 'tags', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'rating']
    
    def get_review_count(self, obj):
        return obj.reviews.count()
    
    def get_average_rating(self, obj):
        from django.db.models import Avg
        avg = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 2) if avg else 0.0


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'product', 'product_name', 'user', 'username', 'rating', 'comment', 'created_at']
        read_only_fields = ['user', 'created_at']
    
    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def create(self, validated_data):
        """Ensure one review per user per product"""
        review, created = Review.objects.update_or_create(
            product=validated_data['product'],
            user=self.context['request'].user,
            defaults={
                'rating': validated_data['rating'],
                'comment': validated_data['comment']
            }
        )
        return review


class RecommendationTaskSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    recommendation_products = serializers.SerializerMethodField()
    
    class Meta:
        model = RecommendationTask
        fields = [
            'id', 'user', 'user_username', 'status', 'task_id',
            'recommendations', 'recommendation_products',
            'error_message', 'created_at', 'started_at',
            'completed_at'
        ]
        read_only_fields = ['task_id', 'created_at', 'started_at', 'completed_at']
    
    def get_recommendation_products(self, obj):
        """Get full product details for recommendations"""
        products = Product.objects.filter(id__in=obj.recommendations)
        return ProductSerializer(products, many=True).data


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    browsing_history_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'email', 'preferences',
            'browsing_history', 'browsing_history_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['browsing_history', 'created_at', 'updated_at']
    
    def get_browsing_history_count(self, obj):
        return len(obj.browsing_history)


class UserBehaviorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = UserBehavior
        fields = [
            'id', 'user', 'username', 'product', 'product_name',
            'event_type', 'timestamp'
        ]
        read_only_fields = ['timestamp']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return data
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('password_confirm')
        
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        return user
