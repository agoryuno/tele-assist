# Use the official Redis image as a base
FROM redis/redis-stack-server:latest

# Copy a custom Redis configuration file that loads the Redisearch module
COPY redis.conf /usr/local/etc/redis/redis.conf

# Expose Redis port
EXPOSE 6379

# Start the Redis server with the custom configuration file
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
