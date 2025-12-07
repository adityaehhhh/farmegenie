import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'aa72a643bbcb59155867609ad39c78a592a98fabdb6bf874'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://farmgenie_user:13L8XhbBpPGLluTaUv43uIDcLBdVAG8f@dpg-d4qhu2c9c44c73bdb5p0-a/farmgenie'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File upload settings
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # Weather API
    WEATHER_API_KEY = "f219aeae857fa3307b394cbccbddca38"
    WEATHER_BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

    # Language settings
    LANGUAGES = {
        'en': 'English',
        'hi': 'Hindi',
        'or': 'Odia',
        'pa': 'Punjabi'
    }
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'Asia/Kolkata'

    # Stripe API Keys (optional for payments)
    STRIPE_PUBLIC_KEY = os.environ.get(
        'STRIPE_PUBLIC_KEY',
        'pk_test_51S6nozJMc0XEvIOCgK2Q2ulGPinfCDybsF0KnZ2t63SKDQZStAkc8maKZkAo9mcUUrixs50liYkwjCpeLUV1X2Kv00w0NLNLvo'
    )
    STRIPE_SECRET_KEY = os.environ.get(
        'STRIPE_SECRET_KEY',
        'sk_test_51S6nozJMc0XEvIOCdTe4m3SkxIC70M1HgvKG8Nv2o4KSufTgxIrfTWkVvTh6dlYNlR3qGZb4JwlBMAHzGssUS17x000SZGAnZA'
    )

    # OpenRouter API configuration
    COHERE_API_KEY = os.environ.get('COHERE_API_KEY') or 'F6dudbIR0DQQ17pI3niD0IVWLYk6Di1Wr5fNxV5k'

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://agri_user:agri@localhost/agri_ai_db'


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://agri_user:agri@localhost/agri_ai_db'
