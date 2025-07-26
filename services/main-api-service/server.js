const express = require('express');
const axios = require('axios');
const redis = require('redis');
const { Pool } = require('pg');
const promClient = require('prom-client');
const helmet = require('helmet');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const compression = require('compression');
const winston = require('winston');

// Initialize Express app
const app = express();
const PORT = process.env.PORT || 3000;

// Configure logging
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
});

// Security middleware
app.use(helmet());
app.use(cors());
app.use(compression());

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP'
});
app.use(limiter);

// Prometheus metrics
const register = new promClient.Registry();
promClient.collectDefaultMetrics({ register });

// Custom metrics
const httpRequestDurationMicroseconds = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'code'],
  buckets: [0.1, 0.3, 0.5, 0.7, 1, 3, 5, 7, 10]
});

const httpRequestsTotal = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'code']
});

register.registerMetric(httpRequestDurationMicroseconds);
register.registerMetric(httpRequestsTotal);

// Database connection
let dbPool;
try {
  dbPool = new Pool({
    host: process.env.DB_HOST || 'postgresql-service',
    port: process.env.DB_PORT || 5432,
    database: process.env.DB_NAME || 'sre_db',
    user: process.env.DB_USER || 'postgres',
    password: process.env.DB_PASSWORD || 'password',
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
  });
} catch (error) {
  logger.error('Database connection failed:', error);
}

// Redis connection
let redisClient;
try {
  const redisUrl = `redis://${process.env.REDIS_HOST || 'redis-service'}:${process.env.REDIS_PORT || 6379}`;

  logger.info(`Redis URL: ${redisUrl}`);

  redisClient = redis.createClient({
    url: redisUrl
  });
  redisClient.connect();
} catch (error) {
  logger.error('Redis connection failed:', error);
}

// Service URLs
const AUTH_SERVICE_URL = process.env.AUTH_SERVICE_URL || 'http://auth-service:8080';
const IMAGE_SERVICE_URL = process.env.IMAGE_SERVICE_URL || 'http://image-service:5000';

// Health check endpoint
app.get('/health', async (req, res) => {
  const health = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    services: {
      database: 'unknown',
      redis: 'unknown',
      auth_service: 'unknown',
      image_service: 'unknown'
    }
  };

  try {
    // Check database
    if (dbPool) {
      await dbPool.query('SELECT 1');
      health.services.database = 'healthy';
    }
  } catch (error) {
    health.services.database = 'unhealthy';
    health.status = 'degraded';
  }

  try {
    // Check Redis
    if (redisClient) {
      await redisClient.ping();
      health.services.redis = 'healthy';
    }
  } catch (error) {
    health.services.redis = 'unhealthy';
    health.status = 'degraded';
  }

  try {
    // Check auth service
    const authResponse = await axios.get(`${AUTH_SERVICE_URL}/health`, { timeout: 5000 });
    health.services.auth_service = authResponse.data.status;
  } catch (error) {
    health.services.auth_service = 'unhealthy';
    health.status = 'degraded';
  }

  try {
    // Check image service
    const imageResponse = await axios.get(`${IMAGE_SERVICE_URL}/health`, { timeout: 5000 });
    health.services.image_service = imageResponse.data.status;
  } catch (error) {
    health.services.image_service = 'unhealthy';
    health.status = 'degraded';
  }

  const statusCode = health.status === 'healthy' ? 200 : 503;
  res.status(statusCode).json(health);
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  try {
    res.set('Content-Type', register.contentType);
    res.end(await register.metrics());
  } catch (error) {
    res.status(500).end(error);
  }
});

// Main API endpoints
app.get('/', (req, res) => {
  res.json({
    message: 'Main API Service - SRE Kubernetes Environment',
    version: '1.0.0',
    endpoints: {
      health: '/health',
      metrics: '/metrics',
      users: '/api/users',
      images: '/api/images'
    }
  });
});

// User management endpoints
app.get('/api/users', async (req, res) => {
  const start = Date.now();
  try {
    // Get users from auth service
    const response = await axios.get(`${AUTH_SERVICE_URL}/users`);
    const duration = Date.now() - start;
    
    httpRequestDurationMicroseconds
      .labels('GET', '/api/users', '200')
      .observe(duration / 1000);
    httpRequestsTotal.labels('GET', '/api/users', '200').inc();
    
    res.json(response.data);
  } catch (error) {
    const duration = Date.now() - start;
    httpRequestDurationMicroseconds
      .labels('GET', '/api/users', '500')
      .observe(duration / 1000);
    httpRequestsTotal.labels('GET', '/api/users', '500').inc();
    
    logger.error('Error fetching users:', error);
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

app.post('/api/users', async (req, res) => {
  const start = Date.now();
  try {
    const response = await axios.post(`${AUTH_SERVICE_URL}/users`, req.body);
    const duration = Date.now() - start;
    
    httpRequestDurationMicroseconds
      .labels('POST', '/api/users', '201')
      .observe(duration / 1000);
    httpRequestsTotal.labels('POST', '/api/users', '201').inc();
    
    res.status(201).json(response.data);
  } catch (error) {
    const duration = Date.now() - start;
    httpRequestDurationMicroseconds
      .labels('POST', '/api/users', '500')
      .observe(duration / 1000);
    httpRequestsTotal.labels('POST', '/api/users', '500').inc();
    
    logger.error('Error creating user:', error);
    res.status(500).json({ error: 'Failed to create user' });
  }
});

// Image management endpoints
app.get('/api/images', async (req, res) => {
  const start = Date.now();
  try {
    const response = await axios.get(`${IMAGE_SERVICE_URL}/images`);
    const duration = Date.now() - start;
    
    httpRequestDurationMicroseconds
      .labels('GET', '/api/images', '200')
      .observe(duration / 1000);
    httpRequestsTotal.labels('GET', '/api/images', '200').inc();
    
    res.json(response.data);
  } catch (error) {
    const duration = Date.now() - start;
    httpRequestDurationMicroseconds
      .labels('GET', '/api/images', '500')
      .observe(duration / 1000);
    httpRequestsTotal.labels('GET', '/api/images', '500').inc();
    
    logger.error('Error fetching images:', error);
    res.status(500).json({ error: 'Failed to fetch images' });
  }
});

app.post('/api/images/upload', async (req, res) => {
  const start = Date.now();
  try {
    const response = await axios.post(`${IMAGE_SERVICE_URL}/upload`, req.body);
    const duration = Date.now() - start;
    
    httpRequestDurationMicroseconds
      .labels('POST', '/api/images/upload', '201')
      .observe(duration / 1000);
    httpRequestsTotal.labels('POST', '/api/images/upload', '201').inc();
    
    res.status(201).json(response.data);
  } catch (error) {
    const duration = Date.now() - start;
    httpRequestDurationMicroseconds
      .labels('POST', '/api/images/upload', '500')
      .observe(duration / 1000);
    httpRequestsTotal.labels('POST', '/api/images/upload', '500').inc();
    
    logger.error('Error uploading image:', error);
    res.status(500).json({ error: 'Failed to upload image' });
  }
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, shutting down gracefully');
  if (dbPool) {
    await dbPool.end();
  }
  if (redisClient) {
    await redisClient.quit();
  }
  process.exit(0);
});

// Start server
app.listen(PORT, () => {
  logger.info(`Main API Service listening on port ${PORT}`);
  logger.info(`Health check available at http://localhost:${PORT}/health`);
  logger.info(`Metrics available at http://localhost:${PORT}/metrics`);
}); 