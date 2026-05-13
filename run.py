from dotenv import load_dotenv
import os

# Load .env before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5050)),
        debug=True
    )
