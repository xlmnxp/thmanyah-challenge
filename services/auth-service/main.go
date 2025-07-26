package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/golang-jwt/jwt/v5"
	_ "github.com/lib/pq"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/sirupsen/logrus"
	"golang.org/x/crypto/bcrypt"
)

// User represents a user in the system
type User struct {
	ID       int    `json:"id"`
	Username string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password,omitempty"`
}

// LoginRequest represents a login request
type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

// HealthResponse represents the health check response
type HealthResponse struct {
	Status    string            `json:"status"`
	Timestamp string            `json:"timestamp"`
	Services  map[string]string `json:"services"`
}

// Global variables
var (
	db          *sql.DB
	redisClient *redis.Client
	logger      *logrus.Logger

	// Prometheus metrics
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "endpoint", "status"},
	)

	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "Duration of HTTP requests in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "endpoint"},
	)

	authAttemptsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "auth_attempts_total",
			Help: "Total number of authentication attempts",
		},
		[]string{"success"},
	)
)

func init() {
	// Initialize logger
	logger = logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})
	logger.SetOutput(os.Stdout)

	// Register Prometheus metrics
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
	prometheus.MustRegister(authAttemptsTotal)

	// Initialize database connection
	dbHost := getEnv("DB_HOST", "postgresql-service")
	dbPort := getEnv("DB_PORT", "5432")
	dbName := getEnv("DB_NAME", "sre_db")
	dbUser := getEnv("DB_USER", "postgres")
	dbPassword := getEnv("DB_PASSWORD", "password")

	psqlInfo := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		dbHost, dbPort, dbUser, dbPassword, dbName)

	var err error
	db, err = sql.Open("postgres", psqlInfo)
	if err != nil {
		logger.Fatal("Failed to connect to database:", err)
	}

	// Test database connection
	if err = db.Ping(); err != nil {
		logger.Fatal("Failed to ping database:", err)
	}

	// Initialize Redis connection
	redisHost := getEnv("REDIS_HOST", "redis-service")
	redisPort := getEnv("REDIS_PORT", "6379")

	redisClient = redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", redisHost, redisPort),
		Password: "",
		DB:       0,
	})

	// Test Redis connection
	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		logger.Fatal("Failed to connect to Redis:", err)
	}

	// Create users table if it doesn't exist
	createTableSQL := `
	CREATE TABLE IF NOT EXISTS users (
		id SERIAL PRIMARY KEY,
		username VARCHAR(50) UNIQUE NOT NULL,
		email VARCHAR(100) UNIQUE NOT NULL,
		password_hash VARCHAR(255) NOT NULL,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);`

	if _, err := db.Exec(createTableSQL); err != nil {
		logger.Fatal("Failed to create users table:", err)
	}

	logger.Info("Auth service initialized successfully")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func generateJWT(userID int, username string) (string, error) {
	secret := getEnv("JWT_SECRET", "your-secret-key")

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"user_id":  userID,
		"username": username,
		"exp":      time.Now().Add(time.Hour * 24).Unix(),
		"iat":      time.Now().Unix(),
	})

	return token.SignedString([]byte(secret))
}

func hashPassword(password string) (string, error) {
	bytes, err := bcrypt.GenerateFromPassword([]byte(password), 14)
	return string(bytes), err
}

func checkPassword(password, hash string) bool {
	err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
	return err == nil
}

func generateRandomString(length int) string {
	b := make([]byte, length)
	rand.Read(b)
	return fmt.Sprintf("%x", b)
}

func main() {
	port := getEnv("PORT", "8080")

	// Set Gin mode
	gin.SetMode(gin.ReleaseMode)

	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(gin.Logger())

	// Middleware for metrics
	router.Use(func(c *gin.Context) {
		start := time.Now()
		c.Next()

		duration := time.Since(start).Seconds()
		status := fmt.Sprintf("%d", c.Writer.Status())

		httpRequestsTotal.WithLabelValues(c.Request.Method, c.FullPath(), status).Inc()
		httpRequestDuration.WithLabelValues(c.Request.Method, c.FullPath()).Observe(duration)
	})

	// Health check endpoint
	router.GET("/health", func(c *gin.Context) {
		health := HealthResponse{
			Status:    "healthy",
			Timestamp: time.Now().Format(time.RFC3339),
			Services: map[string]string{
				"database": "unknown",
				"redis":    "unknown",
			},
		}

		// Check database
		if err := db.Ping(); err != nil {
			health.Services["database"] = "unhealthy"
			health.Status = "degraded"
		} else {
			health.Services["database"] = "healthy"
		}

		// Check Redis
		ctx := context.Background()
		if err := redisClient.Ping(ctx).Err(); err != nil {
			health.Services["redis"] = "unhealthy"
			health.Status = "degraded"
		} else {
			health.Services["redis"] = "healthy"
		}

		statusCode := http.StatusOK
		if health.Status != "healthy" {
			statusCode = http.StatusServiceUnavailable
		}

		c.JSON(statusCode, health)
	})

	// Metrics endpoint
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Root endpoint
	router.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"message": "Authentication Service - SRE Kubernetes Environment",
			"version": "1.0.0",
			"endpoints": gin.H{
				"health":   "/health",
				"metrics":  "/metrics",
				"users":    "/users",
				"login":    "/login",
				"register": "/register",
			},
		})
	})

	// User management endpoints
	router.GET("/users", func(c *gin.Context) {
		rows, err := db.Query("SELECT id, username, email FROM users")
		if err != nil {
			logger.Error("Failed to query users:", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch users"})
			return
		}
		defer rows.Close()

		var users []User
		for rows.Next() {
			var user User
			if err := rows.Scan(&user.ID, &user.Username, &user.Email); err != nil {
				logger.Error("Failed to scan user:", err)
				continue
			}
			users = append(users, user)
		}

		c.JSON(http.StatusOK, users)
	})

	router.POST("/users", func(c *gin.Context) {
		var user User
		if err := c.ShouldBindJSON(&user); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		// Hash password
		hashedPassword, err := hashPassword(user.Password)
		if err != nil {
			logger.Error("Failed to hash password:", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to process password"})
			return
		}

		// Insert user
		var userID int
		err = db.QueryRow(
			"INSERT INTO users (username, email, password_hash) VALUES ($1, $2, $3) RETURNING id",
			user.Username, user.Email, hashedPassword,
		).Scan(&userID)

		if err != nil {
			logger.Error("Failed to create user:", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create user"})
			return
		}

		user.ID = userID
		user.Password = "" // Don't return password

		c.JSON(http.StatusCreated, user)
	})

	// Authentication endpoints
	router.POST("/login", func(c *gin.Context) {
		var loginReq LoginRequest
		if err := c.ShouldBindJSON(&loginReq); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		// Get user from database
		var user User
		var passwordHash string
		err := db.QueryRow(
			"SELECT id, username, email, password_hash FROM users WHERE username = $1",
			loginReq.Username,
		).Scan(&user.ID, &user.Username, &user.Email, &passwordHash)

		if err != nil {
			authAttemptsTotal.WithLabelValues("false").Inc()
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid credentials"})
			return
		}

		// Check password
		if !checkPassword(loginReq.Password, passwordHash) {
			authAttemptsTotal.WithLabelValues("false").Inc()
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid credentials"})
			return
		}

		// Generate JWT token
		token, err := generateJWT(user.ID, user.Username)
		if err != nil {
			logger.Error("Failed to generate JWT:", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to generate token"})
			return
		}

		// Store session in Redis
		sessionID := generateRandomString(32)
		ctx := context.Background()
		err = redisClient.Set(ctx, fmt.Sprintf("session:%s", sessionID), user.ID, time.Hour*24).Err()
		if err != nil {
			logger.Error("Failed to store session:", err)
		}

		authAttemptsTotal.WithLabelValues("true").Inc()

		c.JSON(http.StatusOK, gin.H{
			"token":      token,
			"session_id": sessionID,
			"user": gin.H{
				"id":       user.ID,
				"username": user.Username,
				"email":    user.Email,
			},
		})
	})

	router.POST("/register", func(c *gin.Context) {
		var user User
		if err := c.ShouldBindJSON(&user); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		// Hash password
		hashedPassword, err := hashPassword(user.Password)
		if err != nil {
			logger.Error("Failed to hash password:", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to process password"})
			return
		}

		// Insert user
		var userID int
		err = db.QueryRow(
			"INSERT INTO users (username, email, password_hash) VALUES ($1, $2, $3) RETURNING id",
			user.Username, user.Email, hashedPassword,
		).Scan(&userID)

		if err != nil {
			logger.Error("Failed to create user:", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create user"})
			return
		}

		user.ID = userID
		user.Password = "" // Don't return password

		c.JSON(http.StatusCreated, user)
	})

	// Graceful shutdown
	go func() {
		sigChan := make(chan os.Signal, 1)
		<-sigChan
		logger.Info("Shutting down gracefully...")

		if db != nil {
			db.Close()
		}
		if redisClient != nil {
			redisClient.Close()
		}

		os.Exit(0)
	}()

	logger.Infof("Auth service starting on port %s", port)
	if err := router.Run(":" + port); err != nil {
		logger.Fatal("Failed to start server:", err)
	}
}
