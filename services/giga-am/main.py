#!/usr/bin/env python3
"""
Main entry point for Docker deployment
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    
    try:
        from app import app
        import uvicorn
        
        port = int(os.environ.get('PORT', 7860))
        host = "0.0.0.0"
        
        logger.info(f"Starting application on {host}:{port}")
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
