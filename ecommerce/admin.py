from django.contrib import admin
from django.utils.html import format_html
from ecommerce.models import (
    Product, Category, Review, RecommendationTask,
    UserProfile, UserBehavior
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count', 'created_at']
    search_fields = ['name']
    ordering = ['name']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Number of Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'rating', 'review_count', 'created_at']
    list_filter = ['category', 'created_at', 'rating']
    search_fields = ['name', 'description', 'tags']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'embedding_updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'tags')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'stock')
        }),
        ('Rating & Media', {
            'fields': ('rating', 'image_url')
        }),
        ('ML Data', {
            'fields': ('tfidf_vector', 'embedding_updated_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def review_count(self, obj):
        return obj.reviews.count()
    review_count.short_description = 'Reviews'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating_stars', 'created_at']
    list_filter = ['rating', 'created_at', 'product']
    search_fields = ['user__username', 'product__name', 'comment']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    def rating_stars(self, obj):
        stars = '⭐' * obj.rating
        return format_html(f'<span style="font-size: 1.2em;">{stars}</span>')
    rating_stars.short_description = 'Rating'


@admin.register(RecommendationTask)
class RecommendationTaskAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'user', 'status_badge', 'recommendation_count', 'created_at', 'duration']
    list_filter = ['status', 'created_at']
    search_fields = ['task_id', 'user__username']
    readonly_fields = ['task_id', 'created_at', 'started_at', 'completed_at', 'recommendations']
    ordering = ['-created_at']
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'processing': '#0099FF',
            'completed': '#00CC00',
            'failed': '#FF0000'
        }
        color = colors.get(obj.status, '#999999')
        return format_html(
            f'<span style="background-color: {color}; color: white; padding: 5px 10px; '
            f'border-radius: 3px; font-weight: bold;">{obj.status.upper()}</span>'
        )
    status_badge.short_description = 'Status'
    
    def recommendation_count(self, obj):
        return len(obj.recommendations)
    recommendation_count.short_description = 'Recommendations'
    
    def duration(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return f"{delta.total_seconds():.1f}s"
        return "N/A"
    duration.short_description = 'Duration'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'browsing_history_count', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']
    
    def browsing_history_count(self, obj):
        return len(obj.browsing_history)
    browsing_history_count.short_description = 'Items Viewed'


@admin.register(UserBehavior)
class UserBehaviorAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'event_type', 'timestamp']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['user__username', 'product__name']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        """Prevent manual creation of behavior records"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of behavior records"""
        return False
