"""
Django REST API Views and Serializers
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg
from django.utils import timezone
import uuid

from ecommerce.models import (
    Product, Category, Review, RecommendationTask, 
    UserProfile, UserBehavior
)
from ecommerce.serializers import (
    ProductSerializer, CategorySerializer, ReviewSerializer,
    RecommendationTaskSerializer, UserProfileSerializer
)
from ecommerce.tasks import generate_recommendations, log_user_behavior


class CategoryViewSet(viewsets.ModelViewSet):
    """Category CRUD operations"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in a category"""
        category = self.get_object()
        products = category.products.all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    """Product CRUD and recommendations"""
    queryset = Product.objects.select_related('category').prefetch_related('reviews')
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'rating']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['name', 'price', 'rating', 'created_at']
    ordering = ['-created_at']
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to log view and update product rating"""
        instance = self.get_object()
        
        # Log user interaction if authenticated
        if request.user.is_authenticated:
            log_user_behavior.delay(request.user.id, instance.id, 'view')
        
        # Update average rating from reviews
        avg_rating = instance.reviews.aggregate(avg=Avg('rating'))['avg']
        if avg_rating:
            instance.rating = avg_rating
            instance.save(update_fields=['rating'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def similar(self, request, pk=None):
        """Get similar products (content-based recommendations)"""
        product = self.get_object()
        
        # Call ML service via Celery task
        task_id = str(uuid.uuid4())
        
        task = RecommendationTask.objects.create(
            user=request.user if request.user.is_authenticated else None,
            task_id=task_id,
            status='pending'
        )
        
        # Queue recommendation generation
        if request.user.is_authenticated:
            generate_recommendations.delay(request.user.id, task_id, num_recommendations=5)
            return Response({
                'task_id': task_id,
                'status': 'processing',
                'message': 'Fetching similar products...'
            })
        else:
            # For anonymous users, get similar by category
            similar_products = Product.objects.filter(
                category=product.category
            ).exclude(id=product.id)[:5]
            serializer = ProductSerializer(similar_products, many=True)
            return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products (highest rated)"""
        featured = Product.objects.all().order_by('-rating')[:10]
        serializer = self.get_serializer(featured, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending products (most viewed recently)"""
        from django.db.models import Count
        
        trending = Product.objects.annotate(
            view_count=Count('user_behaviors', filter=Q(user_behaviors__event_type='view'))
        ).order_by('-view_count')[:10]
        
        serializer = self.get_serializer(trending, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Create product (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update product (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)


class ReviewViewSet(viewsets.ModelViewSet):
    """Product reviews"""
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['product', 'user']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        """Create review and log user behavior"""
        review = serializer.save(user=self.request.user)
        log_user_behavior.delay(
            self.request.user.id,
            review.product.id,
            'review'
        )
    
    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """Get current user's reviews"""
        reviews = Review.objects.filter(user=request.user)
        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data)


class RecommendationTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """View recommendation tasks and results"""
    queryset = RecommendationTask.objects.all()
    serializer_class = RecommendationTaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Only show user's own tasks"""
        return RecommendationTask.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate recommendations for current user"""
        num_recommendations = request.data.get('num_recommendations', 5)
        
        # Create task
        task_id = str(uuid.uuid4())
        task = RecommendationTask.objects.create(
            user=request.user,
            task_id=task_id,
            status='pending'
        )
        
        # Queue generation
        generate_recommendations.delay(
            request.user.id,
            task_id,
            num_recommendations
        )
        
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail='pk', methods=['post'], url_path='update')
    def update_task(self, request, pk=None):
        """Update task status (internal use)"""
        task = self.get_object()
        
        status_val = request.data.get('status')
        recommendations = request.data.get('recommendations', [])
        
        if status_val == 'completed':
            task.status = 'completed'
            task.recommendations = recommendations
            task.completed_at = timezone.now()
        elif status_val == 'failed':
            task.status = 'failed'
            task.error_message = request.data.get('error', '')
            task.completed_at = timezone.now()
        
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)


class UserProfileViewSet(viewsets.ViewSet):
    """User profile and preferences"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get current user's profile"""
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'])
    def update_preferences(self, request):
        """Update user preferences"""
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.preferences = request.data.get('preferences', profile.preferences)
        profile.save()
        
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def browsing_history(self, request):
        """Get user's browsing history"""
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        products = Product.objects.filter(id__in=profile.browsing_history)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class SearchViewSet(viewsets.ViewSet):
    """Global search across products"""
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'])
    def products(self, request):
        """Search products by query"""
        query = request.query_params.get('q', '')
        
        if len(query) < 2:
            return Response({'results': []})
        
        # Search in multiple fields
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query) |
            Q(category__name__icontains=query)
        )[:20]
        
        serializer = ProductSerializer(products, many=True)
        return Response({'results': serializer.data, 'count': len(products)})
