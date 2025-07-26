import os
import uuid
import logging
import time
import tempfile
from datetime import datetime
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import boto3
from botocore.exceptions import ClientError
from PIL import Image
import requests

# Set temp directory
tempfile.tempdir = os.getenv('TMPDIR', '/tmp/app-temp')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Environment variables
DB_HOST = os.getenv('DB_HOST', 'postgresql-service')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'sre_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

REDIS_HOST = os.getenv('REDIS_HOST', 'redis-service')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')

MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'minio-service:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'images')

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

IMAGE_UPLOAD_COUNT = Counter(
    'image_uploads_total',
    'Total image uploads',
    ['status']
)

IMAGE_DOWNLOAD_COUNT = Counter(
    'image_downloads_total',
    'Total image downloads',
    ['status']
)

# Initialize connections
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def get_redis_connection():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None

def get_s3_client():
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=f'http://{MINIO_ENDPOINT}',
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            region_name='us-east-1'
        )
        return s3_client
    except Exception as e:
        logger.error(f"S3 client initialization failed: {e}")
        return None

# Initialize database table
def init_database():
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS images (
                        id SERIAL PRIMARY KEY,
                        filename VARCHAR(255) NOT NULL,
                        original_filename VARCHAR(255) NOT NULL,
                        file_size INTEGER NOT NULL,
                        mime_type VARCHAR(100) NOT NULL,
                        s3_key VARCHAR(500) NOT NULL,
                        user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
            logger.info("Database table initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
        finally:
            conn.close()

# Initialize S3 bucket
def init_s3_bucket():
    s3_client = get_s3_client()
    if s3_client:
        try:
            s3_client.head_bucket(Bucket=MINIO_BUCKET)
            logger.info(f"S3 bucket {MINIO_BUCKET} already exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                s3_client.create_bucket(Bucket=MINIO_BUCKET)
                logger.info(f"S3 bucket {MINIO_BUCKET} created successfully")
            else:
                logger.error(f"S3 bucket check failed: {e}")

# Initialize connections on startup
init_database()
init_s3_bucket()

@app.route('/health')
def health_check():
    start_time = time.time()
    
    health = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'database': 'unknown',
            'redis': 'unknown',
            's3': 'unknown'
        }
    }
    
    # Check database
    try:
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
            conn.close()
            health['services']['database'] = 'healthy'
        else:
            health['services']['database'] = 'unhealthy'
            health['status'] = 'degraded'
    except Exception as e:
        health['services']['database'] = 'unhealthy'
        health['status'] = 'degraded'
        logger.error(f"Database health check failed: {e}")
    
    # Check Redis
    try:
        r = get_redis_connection()
        if r:
            r.ping()
            health['services']['redis'] = 'healthy'
        else:
            health['services']['redis'] = 'unhealthy'
            health['status'] = 'degraded'
    except Exception as e:
        health['services']['redis'] = 'unhealthy'
        health['status'] = 'degraded'
        logger.error(f"Redis health check failed: {e}")
    
    # Check S3
    try:
        s3_client = get_s3_client()
        if s3_client:
            s3_client.head_bucket(Bucket=MINIO_BUCKET)
            health['services']['s3'] = 'healthy'
        else:
            health['services']['s3'] = 'unhealthy'
            health['status'] = 'degraded'
    except Exception as e:
        health['services']['s3'] = 'unhealthy'
        health['status'] = 'degraded'
        logger.error(f"S3 health check failed: {e}")
    
    duration = time.time() - start_time
    REQUEST_LATENCY.labels('GET', '/health').observe(duration)
    
    status_code = 200 if health['status'] == 'healthy' else 503
    REQUEST_COUNT.labels('GET', '/health', str(status_code)).inc()
    
    return jsonify(health), status_code

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/')
def index():
    return jsonify({
        'message': 'Image Storage Service - SRE Kubernetes Environment',
        'version': '1.0.0',
        'endpoints': {
            'health': '/health',
            'metrics': '/metrics',
            'images': '/images',
            'upload': '/upload',
            'download': '/download/<image_id>'
        }
    })

@app.route('/images')
def list_images():
    start_time = time.time()
    
    try:
        conn = get_db_connection()
        if not conn:
            REQUEST_COUNT.labels('GET', '/images', '500').inc()
            return jsonify({'error': 'Database connection failed'}), 500
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, filename, original_filename, file_size, mime_type, 
                       user_id, created_at, updated_at
                FROM images
                ORDER BY created_at DESC
            """)
            images = cur.fetchall()
        
        conn.close()
        
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('GET', '/images').observe(duration)
        REQUEST_COUNT.labels('GET', '/images', '200').inc()
        
        return jsonify([dict(img) for img in images])
    
    except Exception as e:
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('GET', '/images').observe(duration)
        REQUEST_COUNT.labels('GET', '/images', '500').inc()
        
        logger.error(f"Error listing images: {e}")
        return jsonify({'error': 'Failed to list images'}), 500

@app.route('/upload', methods=['POST'])
def upload_image():
    start_time = time.time()
    
    try:
        if 'file' not in request.files:
            REQUEST_COUNT.labels('POST', '/upload', '400').inc()
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            REQUEST_COUNT.labels('POST', '/upload', '400').inc()
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
        if not file.filename.lower().endswith(tuple('.' + ext for ext in allowed_extensions)):
            REQUEST_COUNT.labels('POST', '/upload', '400').inc()
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f"uploads/{unique_filename}"
        
        # Read file content
        file_content = file.read()
        file_size = len(file_content)
        
        # Validate image
        try:
            image = Image.open(BytesIO(file_content))
            image.verify()
        except Exception as e:
            REQUEST_COUNT.labels('POST', '/upload', '400').inc()
            return jsonify({'error': 'Invalid image file'}), 400
        
        # Upload to S3
        s3_client = get_s3_client()
        if not s3_client:
            REQUEST_COUNT.labels('POST', '/upload', '500').inc()
            return jsonify({'error': 'S3 service unavailable'}), 500
        
        s3_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type
        )
        
        # Save metadata to database
        conn = get_db_connection()
        if not conn:
            REQUEST_COUNT.labels('POST', '/upload', '500').inc()
            return jsonify({'error': 'Database connection failed'}), 500
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO images (filename, original_filename, file_size, mime_type, s3_key, user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (unique_filename, file.filename, file_size, file.content_type, s3_key, request.form.get('user_id')))
            
            image_id = cur.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # Cache in Redis
        redis_client = get_redis_connection()
        if redis_client:
            cache_key = f"image:{image_id}"
            redis_client.setex(cache_key, 3600, s3_key)  # Cache for 1 hour
        
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('POST', '/upload').observe(duration)
        REQUEST_COUNT.labels('POST', '/upload', '201').inc()
        IMAGE_UPLOAD_COUNT.labels('success').inc()
        
        return jsonify({
            'id': image_id,
            'filename': unique_filename,
            'original_filename': file.filename,
            'file_size': file_size,
            'mime_type': file.content_type,
            's3_key': s3_key
        }), 201
    
    except Exception as e:
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('POST', '/upload').observe(duration)
        REQUEST_COUNT.labels('POST', '/upload', '500').inc()
        IMAGE_UPLOAD_COUNT.labels('error').inc()
        
        logger.error(f"Error uploading image: {e}")
        return jsonify({'error': 'Failed to upload image'}), 500

@app.route('/download/<int:image_id>')
def download_image(image_id):
    start_time = time.time()
    
    try:
        # Get image metadata from database
        conn = get_db_connection()
        if not conn:
            REQUEST_COUNT.labels('GET', '/download', '500').inc()
            return jsonify({'error': 'Database connection failed'}), 500
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT filename, original_filename, mime_type, s3_key
                FROM images
                WHERE id = %s
            """, (image_id,))
            
            image_data = cur.fetchone()
        
        conn.close()
        
        if not image_data:
            REQUEST_COUNT.labels('GET', '/download', '404').inc()
            return jsonify({'error': 'Image not found'}), 404
        
        # Get from S3
        s3_client = get_s3_client()
        if not s3_client:
            REQUEST_COUNT.labels('GET', '/download', '500').inc()
            return jsonify({'error': 'S3 service unavailable'}), 500
        
        try:
            response = s3_client.get_object(Bucket=MINIO_BUCKET, Key=image_data['s3_key'])
            file_content = response['Body'].read()
        except ClientError as e:
            REQUEST_COUNT.labels('GET', '/download', '404').inc()
            return jsonify({'error': 'Image file not found in storage'}), 404
        
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('GET', '/download').observe(duration)
        REQUEST_COUNT.labels('GET', '/download', '200').inc()
        IMAGE_DOWNLOAD_COUNT.labels('success').inc()
        
        return send_file(
            BytesIO(file_content),
            mimetype=image_data['mime_type'],
            as_attachment=True,
            download_name=image_data['original_filename']
        )
    
    except Exception as e:
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('GET', '/download').observe(duration)
        REQUEST_COUNT.labels('GET', '/download', '500').inc()
        IMAGE_DOWNLOAD_COUNT.labels('error').inc()
        
        logger.error(f"Error downloading image: {e}")
        return jsonify({'error': 'Failed to download image'}), 500

@app.route('/images/<int:image_id>', methods=['DELETE'])
def delete_image(image_id):
    start_time = time.time()
    
    try:
        # Get image metadata from database
        conn = get_db_connection()
        if not conn:
            REQUEST_COUNT.labels('DELETE', '/images', '500').inc()
            return jsonify({'error': 'Database connection failed'}), 500
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT s3_key FROM images WHERE id = %s", (image_id,))
            image_data = cur.fetchone()
        
        if not image_data:
            REQUEST_COUNT.labels('DELETE', '/images', '404').inc()
            return jsonify({'error': 'Image not found'}), 404
        
        # Delete from S3
        s3_client = get_s3_client()
        if s3_client:
            try:
                s3_client.delete_object(Bucket=MINIO_BUCKET, Key=image_data['s3_key'])
            except ClientError as e:
                logger.warning(f"Failed to delete from S3: {e}")
        
        # Delete from database
        with conn.cursor() as cur:
            cur.execute("DELETE FROM images WHERE id = %s", (image_id,))
        
        conn.commit()
        conn.close()
        
        # Remove from Redis cache
        redis_client = get_redis_connection()
        if redis_client:
            cache_key = f"image:{image_id}"
            redis_client.delete(cache_key)
        
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('DELETE', '/images').observe(duration)
        REQUEST_COUNT.labels('DELETE', '/images', '200').inc()
        
        return jsonify({'message': 'Image deleted successfully'})
    
    except Exception as e:
        duration = time.time() - start_time
        REQUEST_LATENCY.labels('DELETE', '/images').observe(duration)
        REQUEST_COUNT.labels('DELETE', '/images', '500').inc()
        
        logger.error(f"Error deleting image: {e}")
        return jsonify({'error': 'Failed to delete image'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 