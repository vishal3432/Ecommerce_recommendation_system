# Deployment Guide

## Quick Start with Docker Compose (Recommended)

### Prerequisites
- Docker and Docker Compose installed
- Git installed

### Steps

1. **Clone Repository**
```bash
git clone <your-repo-url>
cd ecommerce-recommendation-system
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your settings:
# - Change SECRET_KEY
# - Set DB_PASSWORD
# - Configure allowed hosts
nano .env
```

3. **Build and Start Services**
```bash
docker-compose up -d
```

4. **Initialize Database**
```bash
docker-compose exec django python manage.py migrate
docker-compose exec django python manage.py createsuperuser
docker-compose exec django python manage.py collectstatic --noinput
```

5. **Verify Services**
```bash
docker-compose ps
# All services should be "healthy"
```

6. **Access Application**
- Django API: http://localhost:8000
- ML Service: http://localhost:8001
- Admin: http://localhost:8000/admin/
- Database: localhost:5432

### View Logs
```bash
docker-compose logs -f django     # Django logs
docker-compose logs -f celery     # Celery worker logs
docker-compose logs -f ml-service # ML service logs
```

---

## Fly.io Deployment

### Prerequisites
- Fly.io account
- Fly CLI installed

### Steps

1. **Initialize Fly App**
```bash
fly launch
# Follow prompts to create app
```

2. **Create Database**
```bash
fly postgres create
# Follow prompts for database setup
```

3. **Create Redis**
```bash
fly redis create
# Follow prompts for Redis setup
```

4. **Set Environment Variables**
```bash
fly secrets set SECRET_KEY=your-secret-key-here
fly secrets set DEBUG=False
fly secrets set ALLOWED_HOSTS=yourdomain.fly.dev
fly secrets set DB_PASSWORD=your-db-password
```

5. **Deploy**
```bash
fly deploy
```

6. **Run Migrations**
```bash
fly ssh console -C "python manage.py migrate"
fly ssh console -C "python manage.py createsuperuser"
```

7. **Monitor**
```bash
fly status
fly logs
```

---

## AWS EC2 Deployment

### Prerequisites
- AWS account with EC2 instance running Ubuntu 22.04
- SSH access to instance

### Steps

1. **Connect to Instance**
```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

2. **Install Dependencies**
```bash
sudo apt update
sudo apt install -y docker.io docker-compose python3-pip git
sudo usermod -aG docker ubuntu
```

3. **Clone and Configure**
```bash
git clone <your-repo-url>
cd ecommerce-recommendation-system
cp .env.example .env
# Edit .env for production
```

4. **Start Services**
```bash
docker-compose up -d
```

5. **Configure Nginx (Optional)**
```bash
sudo apt install -y nginx

# Create /etc/nginx/sites-available/default:
upstream django {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
    }

    location /static/ {
        alias /app/staticfiles/;
    }
}

sudo systemctl reload nginx
```

6. **Setup SSL (Let's Encrypt)**
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## DigitalOcean App Platform

### Steps

1. **Push to GitHub**
```bash
git remote add origin <your-repo-url>
git push origin main
```

2. **Connect on DigitalOcean**
- Go to App Platform
- Create new app
- Connect GitHub repo
- Select repository branch

3. **Add Services**
- Django service (Dockerfile.django)
- ML service (Dockerfile.ml)
- PostgreSQL database
- Redis cache

4. **Set Environment Variables**
- Go to Settings
- Add all variables from .env

5. **Deploy**
- Trigger deployment from DigitalOcean dashboard

---

## Heroku Deployment

⚠️ **Note**: Heroku removed free tier. Consider alternatives.

```bash
# If still using Heroku:
heroku login
heroku create your-app-name
git push heroku main
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
```

---

## Production Checklist

Before deploying to production:

- [ ] Set `DEBUG=False`
- [ ] Generate strong `SECRET_KEY`
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set up Redis properly
- [ ] Configure CORS origins
- [ ] Setup SSL/HTTPS
- [ ] Configure email backend
- [ ] Setup monitoring/logging
- [ ] Configure backups
- [ ] Test all endpoints
- [ ] Load test the system
- [ ] Setup CI/CD pipeline
- [ ] Configure firewall rules
- [ ] Setup health checks
- [ ] Document deployment procedure

---

## Database Backup & Recovery

### Automated Backup
```bash
# In docker-compose.yml:
services:
  backup:
    image: postgres:15-alpine
    entrypoint: bash -c 'while true; do pg_dump -h postgres -U postgres ecommerce_db | gzip > /backup/db_$(date +%Y%m%d_%H%M%S).sql.gz; sleep 86400; done'
    volumes:
      - backup:/backup
    depends_on:
      - postgres
```

### Manual Backup
```bash
docker-compose exec postgres pg_dump -U postgres ecommerce_db > backup.sql
```

### Restore
```bash
cat backup.sql | docker-compose exec -T postgres psql -U postgres ecommerce_db
```

---

## Monitoring & Alerts

### Health Checks
```bash
# Django health
curl http://localhost:8000/api/health/

# ML service health
curl http://localhost:8001/health

# Database
docker-compose exec postgres pg_isready
```

### Monitoring Tools
- **Sentry**: Error tracking
- **NewRelic**: Performance monitoring
- **DataDog**: Infrastructure monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Visualization

### Setup Example (Sentry)
```python
# In django_app/settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
)
```

---

## Troubleshooting

### Services won't start
```bash
docker-compose down
docker-compose up --build -d
docker-compose logs -f
```

### Database connection issues
```bash
docker-compose exec postgres psql -U postgres -c "SELECT 1"
# Should return: 1
```

### Celery tasks not running
```bash
docker-compose restart celery celery-beat
docker-compose logs celery
```

### WebSocket not working
- Check `ALLOWED_HOSTS`
- Verify Redis connection
- Check Channels configuration
- Review browser console errors

### ML service timeout
- Increase timeout in FastAPI
- Check model size
- Monitor memory usage
- Consider batch processing

---

## Scaling Tips

1. **Increase Celery Workers**
   - Modify `docker-compose.yml` worker concurrency
   - Add multiple worker containers

2. **Database Optimization**
   - Add indexes on frequently queried fields
   - Use query optimization techniques
   - Consider read replicas for scaling reads

3. **Caching**
   - Cache product recommendations (TTL: 1 hour)
   - Cache product details (TTL: 24 hours)
   - Use Redis efficiently

4. **Load Balancing**
   - Use Nginx reverse proxy
   - Setup multiple Django instances
   - Distribute with HAProxy or AWS load balancer

5. **CDN for Static Files**
   - Serve static files from CloudFront
   - Setup S3 bucket for media files

---

## Rollback Procedure

```bash
# View previous deployment
docker-compose images

# Rollback to previous version
git revert HEAD
docker-compose up -d --build

# Or specific version
git checkout <previous-commit>
docker-compose up -d --build
```

---

For more detailed instructions, see the main README.md file.
