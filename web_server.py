import asyncio
import logging
from aiohttp import web
from threading import Thread
import os

logger = logging.getLogger(__name__)

class HealthCheckServer:
    def __init__(self, port=None):
        self.port = port or int(os.environ.get('PORT', 10000))
        self.app = web.Application()
        self.app.router.add_get('/', self.serve_index)
        self.app.router.add_get('/health', self.health_check)
        self.runner = None
        
    async def serve_index(self, request):
        """Serve the index.html file"""
        try:
            with open('index.html', 'r') as f:
                html_content = f.read()
            return web.Response(text=html_content, content_type='text/html')
        except FileNotFoundError:
            return web.Response(
                text='Nagger Bot is running! Visit https://t.me/Naggering_Bot to use the bot.',
                content_type='text/plain'
            )
    
    async def health_check(self, request):
        """Simple health check endpoint"""
        return web.Response(
            text='OK',
            content_type='text/plain'
        )
    
    async def start(self):
        """Start the web server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health check server started on port {self.port}")
    
    async def stop(self):
        """Stop the web server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")

def run_health_server():
    """Run the health check server in a separate thread"""
    async def run():
        server = HealthCheckServer()
        await server.start()
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())
