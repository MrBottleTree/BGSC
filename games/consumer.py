from channels.generic.websocket import AsyncWebsocketConsumer
import json

class LiveFeed(AsyncWebsocketConsumer):
    async def connect(self):
        self.group = "live"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data):
        pass

    async def push_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
