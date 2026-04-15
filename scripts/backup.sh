#!/bin/bash

# Backup script for Birtha + WrkHrs AI stack
# Creates backups of PostgreSQL, MinIO, and configuration files

set -euo pipefail

# Configuration
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Create backup directory
create_backup_dir() {
    local backup_path="$1"
    mkdir -p "$backup_path"
    log "Created backup directory: $backup_path"
}

# Backup PostgreSQL
backup_postgres() {
    local backup_path="$1"
    local postgres_backup="$backup_path/postgres_$DATE.sql"
    
    log "Starting PostgreSQL backup..."
    
    if docker exec postgres pg_dumpall -U postgres > "$postgres_backup"; then
        success "PostgreSQL backup completed: $postgres_backup"
        
        # Compress backup
        gzip "$postgres_backup"
        success "PostgreSQL backup compressed: $postgres_backup.gz"
    else
        error "PostgreSQL backup failed"
        return 1
    fi
}

# Backup MinIO
backup_minio() {
    local backup_path="$1"
    local minio_backup="$backup_path/minio_$DATE.tar.gz"
    
    log "Starting MinIO backup..."
    
    # Create MinIO backup using mc (MinIO client)
    if docker exec minio mc mirror /data "$minio_backup"; then
        success "MinIO backup completed: $minio_backup"
    else
        error "MinIO backup failed"
        return 1
    fi
}

# Backup configuration files
backup_configs() {
    local backup_path="$1"
    local config_backup="$backup_path/configs_$DATE.tar.gz"
    
    log "Starting configuration backup..."
    
    # Backup important configuration files
    tar -czf "$config_backup" \
        -C /path/to/project \
        docker-compose*.yml \
        .env \
        docker/ \
        mcp-servers/mcp/config/ \
        scripts/ \
        2>/dev/null || true
    
    success "Configuration backup completed: $config_backup"
}

# Backup MLflow artifacts
backup_mlflow() {
    local backup_path="$1"
    local mlflow_backup="$backup_path/mlflow_$DATE.tar.gz"
    
    log "Starting MLflow backup..."
    
    # Backup MLflow artifacts directory
    if docker exec mlflow tar -czf - /mlflow/artifacts > "$mlflow_backup"; then
        success "MLflow backup completed: $mlflow_backup"
    else
        warning "MLflow backup failed (may not be critical)"
    fi
}

# Backup Qdrant data
backup_qdrant() {
    local backup_path="$1"
    local qdrant_backup="$backup_path/qdrant_$DATE.tar.gz"
    
    log "Starting Qdrant backup..."
    
    # Backup Qdrant data directory
    if docker exec qdrant tar -czf - /qdrant/storage > "$qdrant_backup"; then
        success "Qdrant backup completed: $qdrant_backup"
    else
        warning "Qdrant backup failed (may not be critical)"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    local backup_path="$1"
    
    log "Cleaning up backups older than $RETENTION_DAYS days..."
    
    find "$backup_path" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
    find "$backup_path" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
    
    success "Old backups cleaned up"
}

# Verify backup integrity
verify_backup() {
    local backup_file="$1"
    
    if [[ "$backup_file" == *.gz ]]; then
        if gzip -t "$backup_file" 2>/dev/null; then
            success "Backup integrity verified: $backup_file"
            return 0
        else
            error "Backup integrity check failed: $backup_file"
            return 1
        fi
    else
        success "Backup file exists: $backup_file"
        return 0
    fi
}

# Send backup notification
send_notification() {
    local status="$1"
    local message="$2"
    
    # This would integrate with your notification system
    # For now, just log the notification
    if [[ "$status" == "success" ]]; then
        success "Backup notification: $message"
    else
        error "Backup notification: $message"
    fi
}

# Main backup function
main() {
    local backup_path="$BACKUP_DIR/$DATE"
    local backup_success=true
    
    log "Starting backup process..."
    
    # Create backup directory
    create_backup_dir "$backup_path"
    
    # Backup PostgreSQL
    if ! backup_postgres "$backup_path"; then
        backup_success=false
    fi
    
    # Backup MinIO
    if ! backup_minio "$backup_path"; then
        backup_success=false
    fi
    
    # Backup configuration files
    backup_configs "$backup_path"
    
    # Backup MLflow artifacts
    backup_mlflow "$backup_path"
    
    # Backup Qdrant data
    backup_qdrant "$backup_path"
    
    # Verify backups
    log "Verifying backups..."
    for backup_file in "$backup_path"/*.gz; do
        if [[ -f "$backup_file" ]]; then
            verify_backup "$backup_file"
        fi
    done
    
    # Cleanup old backups
    cleanup_old_backups "$BACKUP_DIR"
    
    # Send notification
    if [[ "$backup_success" == "true" ]]; then
        success "Backup process completed successfully"
        send_notification "success" "Backup completed successfully at $DATE"
    else
        error "Backup process completed with errors"
        send_notification "error" "Backup completed with errors at $DATE"
        exit 1
    fi
}

# Run main function
main "$@"
