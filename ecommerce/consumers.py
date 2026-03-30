"""
Django Channels WebSocket Consumer for Real-time Notifications
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class RecommendationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time recommendation updates"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.user_id = self.user.id
        self.group_name = f'user_{self.user_id}'
        
        # Join user group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected for user {self.user_id}")
        
        # Send connection confirmation
        await self.send(json.dumps({
            'type': 'connection',
            'status': 'connected',
            'user_id': self.user_id,
            'message': 'Connected to recommendation service'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"WebSocket disconnected for user {self.user_id}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Handle ping/pong for connection keep-alive
                await self.send(json.dumps({'type': 'pong'}))
            
            elif message_type == 'generate_recommendations':
                # Queue recommendation generation
                await self.handle_recommendation_request(data)
            
            elif message_type == 'cancel_task':
                # Cancel a pending task
                await self.handle_cancel_task(data)
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await self.send_error(f"Error: {str(e)}")
    
    async def recommendation_update(self, event):
        """Handle recommendation update messages from the group"""
        content = event.get('content', {})
        
        # Send update to WebSocket
        await self.send(json.dumps(content))
    
    async def handle_recommendation_request(self, data):
        """Handle recommendation generation request"""
        from ecommerce.tasks import generate_recommendations
        from ecommerce.models import RecommendationTask
        import uuid
        
        try:
            num_recommendations = data.get('num_recommendations', 5)
            product_id = data.get('product_id')
            
            # Create task
            task_id = str(uuid.uuid4())
            
            task = await database_sync_to_async(RecommendationTask.objects.create)(
                user_id=self.user_id,
                task_id=task_id,
                status='pending'
            )
            
            # Queue recommendation generation
            generate_recommendations.delay(
                self.user_id,
                task_id,
                num_recommendations
            )
            
            # Send confirmation
            await self.send(json.dumps({
                'type': 'recommendation_queued',
                'task_id': task_id,
                'status': 'pending',
                'message': 'Generating recommendations...'
            }))
            
            logger.info(f"Recommendation task {task_id} queued for user {self.user_id}")
        
        except Exception as e:
            logger.error(f"Error creating recommendation task: {str(e)}")
            await self.send_error(f"Failed to create recommendation task: {str(e)}")
    
    async def handle_cancel_task(self, data):
        """Handle task cancellation"""
        from ecommerce.models import RecommendationTask
        
        try:
            task_id = data.get('task_id')
            
            task = await database_sync_to_async(
                RecommendationTask.objects.filter(task_id=task_id, user_id=self.user_id).first
            )()
            
            if task:
                if task.status == 'pending':
                    task.status = 'failed'
                    task.error_message = 'Cancelled by user'
                    await database_sync_to_async(task.save)()
                    
                    await self.send(json.dumps({
                        'type': 'task_cancelled',
                        'task_id': task_id,
                        'message': 'Task cancelled successfully'
                    }))
                else:
                    await self.send_error(f"Cannot cancel task in {task.status} status")
            else:
                await self.send_error("Task not found")
        
        except Exception as e:
            logger.error(f"Error cancelling task: {str(e)}")
            await self.send_error(f"Failed to cancel task: {str(e)}")
    
    async def send_error(self, message):
        """Send error message to client"""
        await self.send(json.dumps({
            'type': 'error',
            'message': message
        }))


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for general notifications"""
    
    async def connect(self):
        """Handle connection"""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.user_id = self.user.id
        self.notification_group = f'notifications_user_{self.user_id}'
        
        # Join notification group
        await self.channel_layer.group_add(
            self.notification_group,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Notification connection for user {self.user_id}")
    
    async def disconnect(self, close_code):
        """Handle disconnection"""
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(
                self.notification_group,
                self.channel_name
            )
    
    async def notification_message(self, event):
        """Handle notification messages"""
        notification = event.get('notification', {})
        
        await self.send(json.dumps({
            'type': 'notification',
            'data': notification
        }))
