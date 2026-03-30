from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from ecommerce.models import Product, Review, UserProfile
from ecommerce.tasks import train_ml_model, log_user_behavior


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile when user is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Product)
def product_updated(sender, instance, created, **kwargs):
    """Retrain ML model when product is added/updated"""
    # Queue model training (debounced - won't run too frequently)
    train_ml_model.apply_async(countdown=60)  # Run after 1 minute


@receiver(post_save, sender=Review)
def update_product_rating(sender, instance, created, **kwargs):
    """Update product rating when review is created"""
    from django.db.models import Avg
    
    product = instance.product
    avg_rating = product.reviews.aggregate(avg=Avg('rating'))['avg']
    if avg_rating:
        product.rating = avg_rating
        product.save(update_fields=['rating'])
