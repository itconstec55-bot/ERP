import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger('accounting')


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        self.group_name = f'user_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get('type', '')
            if msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            pass

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'title': event.get('title', ''),
            'message': event.get('message', ''),
            'level': event.get('level', 'info'),
            'url': event.get('url', ''),
            'created_at': event.get('created_at', ''),
        }))

    async def tax_invoice_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'tax_invoice_status',
            'invoice_id': str(event.get('invoice_id', '')),
            'invoice_number': event.get('invoice_number', ''),
            'status': event.get('status', ''),
            'message': event.get('message', ''),
        }))
