"""
Celery Tasks for Asynchronous Processing
- Background recommendation generation
- Model training and updates
- User behavior logging
- Email notifications
"""

from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import requests
from datetime import datetime, timedelta
import json

from ecommerce.models import (
    Product, RecommendationTask, UserBehavior, 
    UserProfile, Category
)

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


@shared_task(bind=True, max_retries=3)
def generate_recommendations(self, user_id: int, task_id: str, num_recommendations: int = 5):
    """
    Generate product recommendations for a user
    
    Args:
        user_id: Django user ID
        task_id: Recommendation task ID
        num_recommendations: Number of recommendations to generate
    """
    try:
        logger.info(f"Starting recommendation generation for user {user_id}, task {task_id}")
        
        # Get user profile and browsing history
        user_profile = UserProfile.objects.get(user_id=user_id)
        
        # Update task status to processing
        task = RecommendationTask.objects.get(task_id=task_id)
        task.status = 'processing'
        task.started_at = timezone.now()
        task.save()
        
        # Notify user via WebSocket (processing started)
        send_websocket_notification(
            user_id=user_id,
            status='processing',
            message='Generating recommendations...',
            task_id=task_id
        )
        
        # Prepare request for ML service
        ml_request = {
            'user_id': user_id,
            'browsing_history': user_profile.browsing_history,
            'num_recommendations': num_recommendations,
            'task_id': task_id
        }
        
        # Call FastAPI ML service
        ml_service_url = 'http://localhost:8001'  # Should be from settings
        response = requests.post(
            f'{ml_service_url}/recommend',
            json=ml_request,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"ML Service error: {response.text}")
        
        result = response.json()
        recommendations = [r['id'] for r in result.get('recommendations', [])]
        
        # Update task with results
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.recommendations = recommendations
        task.save()
        
        logger.info(f"Recommendations completed for task {task_id}: {recommendations}")
        
        # Notify user via WebSocket (completed)
        send_websocket_notification(
            user_id=user_id,
            status='completed',
            message='Recommendations ready!',
            task_id=task_id,
            data={'recommendations': recommendations}
        )
        
        return {
            'status': 'success',
            'task_id': task_id,
            'recommendations': recommendations
        }
        
    except Exception as exc:
        logger.error(f"Recommendation generation error: {str(exc)}")
        
        # Mark task as failed
        try:
            task = RecommendationTask.objects.get(task_id=task_id)
            task.status = 'failed'
            task.error_message = str(exc)
            task.completed_at = timezone.now()
            task.save()
        except:
            pass
        
        # Notify user of failure
        send_websocket_notification(
            user_id=user_id,
            status='failed',
            message=f'Error generating recommendations: {str(exc)}',
            task_id=task_id
        )
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task
def train_ml_model():
    """
    Train the ML recommendation model with all products
    Called periodically or when products are updated
    """
    try:
        logger.info("Starting ML model training")
        
        # Fetch all products
        products = Product.objects.all()
        product_data = [
            {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'category': p.category.name,
                'tags': p.tags,
                'rating': p.rating
            }
            for p in products
        ]
        
        if not product_data:
            logger.warning("No products to train on")
            return {'status': 'no_data'}
        
        # Send to ML service for training
        ml_service_url = 'http://localhost:8001'
        response = requests.post(
            f'{ml_service_url}/train',
            json={'products': product_data},
            timeout=60
        )
        
        if response.status_code == 200:
            logger.info(f"Model training completed successfully")
            return {'status': 'success', 'products_trained': len(product_data)}
        else:
            raise Exception(f"ML service training failed: {response.text}")
            
    except Exception as e:
        logger.error(f"Model training error: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def log_user_behavior(user_id: int, product_id: int, event_type: str):
    """
    Log user behavior for analytics and model training
    
    Args:
        user_id: Django user ID
        product_id: Product ID
        event_type: Type of interaction (view, click, cart, purchase, review)
    """
    try:
        from django.contrib.auth.models import User
        
        user = User.objects.get(id=user_id)
        product = Product.objects.get(id=product_id)
        
        # Create behavior record
        UserBehavior.objects.create(
            user=user,
            product=product,
            event_type=event_type
        )
        
        # Update user browsing history if view event
        if event_type == 'view':
            user_profile, _ = UserProfile.objects.get_or_create(user=user)
            user_profile.add_to_browsing_history(product_id)
        
        logger.info(f"Logged {event_type} event for user {user_id}, product {product_id}")
        
    except Exception as e:
        logger.error(f"Error logging behavior: {str(e)}")


@shared_task
def clean_old_tasks():
    """
    Clean up old recommendation tasks (older than 30 days)
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count, _ = RecommendationTask.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned {deleted_count} old recommendation tasks")
        return {'deleted': deleted_count}
        
    except Exception as e:
        logger.error(f"Error cleaning tasks: {str(e)}")


@shared_task
def send_recommendation_email(user_id: int, recommendations: list):
    """
    Send personalized recommendation email to user
    
    Args:
        user_id: Django user ID
        recommendations: List of product IDs to recommend
    """
    try:
        from django.contrib.auth.models import User
        
        user = User.objects.get(id=user_id)
        products = Product.objects.filter(id__in=recommendations)
        
        # Build email content
        product_list = "\n".join([
            f"- {p.name}: ${p.price} (Rating: {p.rating}/5)"
            for p in products
        ])
        
        message = f"""
        Hi {user.first_name or user.username},
        
        Based on your browsing history, we've selected these products for you:
        
        {product_list}
        
        Visit our store to view these and more!
        
        Best regards,
        The E-commerce Team
        """
        
        send_mail(
            subject='Personalized Product Recommendations',
            message=message,
            from_email='noreply@ecommerce.local',
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"Sent recommendation email to {user.email}")
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")


@shared_task
def batch_generate_recommendations(limit: int = 100):
    """
    Generate recommendations for multiple users
    (Called periodically for all active users)
    
    Args:
        limit: Maximum number of users to process
    """
    try:
        from django.contrib.auth.models import User
        
        # Get active users (who logged in recently)
        cutoff_date = timezone.now() - timedelta(days=7)
        active_users = User.objects.filter(last_login__gte=cutoff_date)[:limit]
        
        generated_count = 0
        for user in active_users:
            # Create recommendation task
            import uuid
            task_id = str(uuid.uuid4())
            
            task = RecommendationTask.objects.create(
                user=user,
                task_id=task_id,
                status='pending'
            )
            
            # Queue recommendation generation
            generate_recommendations.delay(user.id, task_id)
            generated_count += 1
        
        logger.info(f"Queued recommendations for {generated_count} users")
        return {'queued': generated_count}
        
    except Exception as e:
        logger.error(f"Batch recommendation error: {str(e)}")
        return {'error': str(e)}


def send_websocket_notification(user_id: int, status: str, message: str, task_id: str, data: dict = None):
    """
    Send real-time notification via WebSocket
    
    Args:
        user_id: Django user ID
        status: Status message (processing, completed, failed)
        message: Human-readable message
        task_id: Recommendation task ID
        data: Additional data to send
    """
    try:
        notification = {
            'type': 'recommendation_update',
            'status': status,
            'message': message,
            'task_id': task_id,
            'timestamp': timezone.now().isoformat(),
            'data': data or {}
        }
        
        # Send via WebSocket to user's channel
        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}',
            {
                'type': 'recommendation_update',
                'content': notification
            }
        )
        
        logger.info(f"Sent WebSocket notification to user {user_id}: {status}")
        
    except Exception as e:
        logger.warning(f"Error sending WebSocket notification: {str(e)}")
